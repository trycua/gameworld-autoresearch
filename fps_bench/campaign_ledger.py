"""Controller-owned, single-host campaign accounting; never share SQLite over NFS."""

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import time


class BudgetRefused(RuntimeError):
    pass


class LedgerConflict(RuntimeError):
    pass


LIMITS = {
    "modal_micro_usd": (2_000_000_000, 1_800_000_000),
    "litellm_tokens": (1_000_000_000, 1_000_000_000),
}


def positive_integer(value, name, allow_zero=False):
    if type(value) is not int or value < (0 if allow_zero else 1):
        raise ValueError(f"{name} must be an integer >= {0 if allow_zero else 1}")


def accounting_totals(snapshot):
    totals = {}
    for resource in LIMITS:
        observed = sum(row["actual"] for row in snapshot["reservations"]
                       if row["resource"] == resource and row["state"] == "settled")
        observed += sum(row["actual"] for row in snapshot["prior_usage"] if row["resource"] == resource)
        reserved = sum(row["amount"] for row in snapshot["reservations"]
                       if row["resource"] == resource and row["state"] == "held")
        retired = sum(row["amount"] for row in snapshot["reservations"]
                      if row["resource"] == resource and row["state"] == "retired_token_policy")
        if resource == "modal_micro_usd":
            groups = snapshot.get("reconciled_modal_groups", [])
            observed += sum(row["observed"] for row in groups)
            reserved += sum(max(0, row["floor"] - row["observed"]) for row in groups)
        if observed + reserved + retired != snapshot["resources"][resource]["committed"]:
            raise LedgerConflict("Telemetry accounting does not match committed allowance")
        totals[resource] = {"observed": observed, "reserved": reserved}
        if retired:
            totals[resource]["retired_unmeasured"] = retired
    return totals


class CampaignLedger:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def transaction(self):
        connection = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except BaseException:
            if connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            connection.close()

    def initialize(self, campaign):
        if not isinstance(campaign, str) or not campaign.strip():
            raise ValueError("campaign must be nonempty")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS campaign "
                               "(id TEXT PRIMARY KEY, frozen INTEGER NOT NULL, reason TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS limits "
                               "(resource TEXT PRIMARY KEY, total INTEGER NOT NULL, normal INTEGER NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS reservations "
                               "(id TEXT PRIMARY KEY, resource TEXT NOT NULL REFERENCES limits(resource), "
                               "amount INTEGER NOT NULL, purpose TEXT NOT NULL, expires_at INTEGER NOT NULL, "
                               "state TEXT NOT NULL, actual INTEGER, receipt TEXT UNIQUE)")
            connection.execute("CREATE TABLE IF NOT EXISTS events "
                               "(sequence INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER NOT NULL, "
                               "kind TEXT NOT NULL, payload TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS prior_usage "
                               "(id TEXT PRIMARY KEY, resource TEXT NOT NULL REFERENCES limits(resource), "
                               "actual INTEGER NOT NULL, latest_actual INTEGER NOT NULL, receipt TEXT NOT NULL)")
            current = connection.execute("SELECT id FROM campaign").fetchone()
            if current:
                if current["id"] != campaign:
                    raise LedgerConflict("Database belongs to another campaign; cannot reset usage")
                stored = {row["resource"]: (row["total"], row["normal"])
                          for row in connection.execute("SELECT * FROM limits")}
                if stored != LIMITS:
                    raise LedgerConflict("Persisted limits differ from approved campaign limits")
                return
            connection.execute("INSERT INTO campaign VALUES (?,0,'')", (campaign,))
            connection.executemany("INSERT INTO limits VALUES (?,?,?)",
                                   [(resource, *limits) for resource, limits in LIMITS.items()])
            self._event(connection, "initialized", {"campaign": campaign, "limits": LIMITS})

    @staticmethod
    def _event(connection, kind, payload):
        connection.execute("INSERT INTO events(timestamp,kind,payload) VALUES (?,?,?)",
                           (int(time.time()), kind, json.dumps(payload, sort_keys=True)))

    @staticmethod
    def _prior_rows(connection):
        if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='prior_usage'").fetchone():
            return [dict(row) for row in connection.execute("SELECT * FROM prior_usage ORDER BY id")]
        return []

    @staticmethod
    def _usage(connection, resource):
        rows = connection.execute("SELECT * FROM reservations WHERE resource=?", (resource,)).fetchall()
        committed = sum(row["actual"] if row["state"] == "settled" else row["amount"] for row in rows)
        normal = sum(row["actual"] if row["state"] == "settled" else row["amount"]
                     for row in rows if row["purpose"] == "normal")
        prior = sum(row["actual"] for row in CampaignLedger._prior_rows(connection) if row["resource"] == resource)
        excess = 0
        if resource == "modal_micro_usd" and connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='modal_reconciliation_groups'").fetchone():
            excess = connection.execute("SELECT COALESCE(SUM(excess),0) FROM modal_reconciliation_groups").fetchone()[0]
        return committed + prior + excess, normal + prior + excess

    def reserve(self, reservation_id, resource, amount, expires_at, purpose="normal"):
        with self.transaction() as connection:
            return self._reserve_in_transaction(connection, reservation_id, resource, amount, expires_at, purpose)

    @staticmethod
    def _tokens_disabled(connection):
        return bool(connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='token_budget_removal'"
        ).fetchone() and connection.execute("SELECT 1 FROM token_budget_removal").fetchone())

    def remove_token_budget(self):
        with self.transaction() as connection:
            if self._tokens_disabled(connection):
                return {"removed": True, "already_removed": True}
            campaign = connection.execute("SELECT * FROM campaign").fetchone()
            if campaign is None:
                raise LedgerConflict("Existing campaign required")
            connection.execute("CREATE TABLE IF NOT EXISTS token_budget_removal ("
                               "singleton INTEGER PRIMARY KEY CHECK(singleton=1), authorization TEXT NOT NULL)")
            connection.execute("INSERT INTO token_budget_removal VALUES (1,?)",
                               ("User removed token budgets; monitor existing LiteLLM telemetry",))
            retired = [row['id'] for row in connection.execute(
                "SELECT id FROM reservations WHERE resource='litellm_tokens' AND state='held' ORDER BY id")]
            connection.execute("UPDATE reservations SET state='retired_token_policy' "
                               "WHERE resource='litellm_tokens' AND state='held'")
            prefix = "Ambiguous upstream usage for "
            dispatch = campaign['reason'].removeprefix(prefix)
            total, normal = self._usage(connection, 'modal_micro_usd')
            limits = connection.execute("SELECT total,normal FROM limits WHERE resource='modal_micro_usd'").fetchone()
            modal_overrun = connection.execute(
                "SELECT 1 FROM reservations WHERE resource='modal_micro_usd' AND actual>amount").fetchone()
            if connection.execute("SELECT 1 FROM sqlite_master WHERE name='modal_reconciliation_groups'").fetchone():
                modal_overrun = modal_overrun or connection.execute(
                    "SELECT 1 FROM modal_reconciliation_groups WHERE excess>0").fetchone()
            modal_safe = total <= limits['total'] and normal <= limits['normal'] and not modal_overrun
            cleared = bool(campaign['frozen'] and campaign['reason'].startswith(prefix)
                           and dispatch in retired and modal_safe)
            if cleared:
                connection.execute("UPDATE campaign SET frozen=0,reason=''")
            result = {"removed": True, "retired_reservations": retired, "token_freeze_cleared": cleared,
                      "measured_usage_claimed": False, "modal_policy_changed": False}
            self._event(connection, "token_budget_removed", result)
            return result

    def _reserve_in_transaction(self, connection, reservation_id, resource, amount, expires_at, purpose="normal"):
        positive_integer(amount, "amount")
        positive_integer(expires_at, "expires_at")
        if not isinstance(reservation_id, str) or not reservation_id.strip():
            raise ValueError("reservation_id must be nonempty")
        if resource not in LIMITS or purpose not in ("normal", "shutdown"):
            raise ValueError("Unknown resource or purpose")
        if resource == "litellm_tokens" and self._tokens_disabled(connection):
            raise BudgetRefused("Token reservations are disabled; use LiteLLM telemetry")
        if resource != "modal_micro_usd" and purpose != "normal":
            raise ValueError("Shutdown reserve is only for Modal")
        existing = connection.execute("SELECT * FROM reservations WHERE id=?", (reservation_id,)).fetchone()
        if existing:
            if any(existing[key] != value for key, value in {
                "resource": resource, "amount": amount, "expires_at": expires_at, "purpose": purpose
            }.items()):
                raise LedgerConflict("Idempotency key reused with different reservation")
            return dict(existing)
        campaign = connection.execute("SELECT * FROM campaign").fetchone()
        if campaign["frozen"]:
            raise BudgetRefused(f"Campaign frozen: {campaign['reason']}")
        if expires_at <= int(time.time()):
            raise BudgetRefused("Reservation must have a future deadline")
        stale = connection.execute("SELECT id FROM reservations WHERE state='held' AND expires_at<=?",
                                   (int(time.time()),)).fetchone()
        if stale:
            raise BudgetRefused(f"Unreconciled expired reservation: {stale['id']}")
        total, normal = self._usage(connection, resource)
        limits = connection.execute("SELECT * FROM limits WHERE resource=?", (resource,)).fetchone()
        shutdown_exceeded = purpose == "shutdown" and total - normal + amount > limits["total"] - limits["normal"]
        if (total + amount > limits["total"]
                or (purpose == "normal" and normal + amount > limits["normal"])
                or shutdown_exceeded):
            raise BudgetRefused(f"Insufficient campaign allowance for {resource}")
        connection.execute("INSERT INTO reservations VALUES (?,?,?,?,?,'held',NULL,NULL)",
                           (reservation_id, resource, amount, purpose, expires_at))
        self._event(connection, "reserved", {"id": reservation_id, "resource": resource,
                                             "amount": amount, "purpose": purpose, "expires_at": expires_at})
        return dict(connection.execute("SELECT * FROM reservations WHERE id=?", (reservation_id,)).fetchone())

    def settle(self, reservation_id, actual, receipt):
        with self.transaction() as connection:
            return self._settle_in_transaction(connection, reservation_id, actual, receipt)

    def _settle_in_transaction(self, connection, reservation_id, actual, receipt):
        positive_integer(actual, "actual", allow_zero=True)
        if not isinstance(receipt, str) or not receipt.strip():
            raise ValueError("A provider reconciliation receipt is required, including for zero usage")
        row = connection.execute("SELECT * FROM reservations WHERE id=?", (reservation_id,)).fetchone()
        if row is None:
            raise LedgerConflict("Unknown reservation")
        if row["state"] == "settled":
            if row["actual"] != actual or row["receipt"] != receipt:
                raise LedgerConflict("Settled usage is immutable")
            return dict(row)
        if row["state"] != "held":
            raise LedgerConflict("Reconciled retained allocations cannot be refunded through settlement")
        used = connection.execute("SELECT id FROM reservations WHERE receipt=?", (receipt,)).fetchone()
        if used:
            raise LedgerConflict("Receipt already used for another reservation")
        connection.execute("UPDATE reservations SET state='settled',actual=?,receipt=? WHERE id=?",
                           (actual, receipt, reservation_id))
        if actual > row["amount"]:
            connection.execute("UPDATE campaign SET frozen=1,reason=?",
                               (f"Usage exceeded reservation {reservation_id}",))
        self._event(connection, "settled", {"id": reservation_id, "actual": actual, "receipt": receipt,
                                            "overrun": actual > row["amount"]})
        return dict(connection.execute("SELECT * FROM reservations WHERE id=?", (reservation_id,)).fetchone())

    def record_prior_usage(self, usage_id, resource, actual, receipt):
        """Import authenticated pre-admission costs; never use for already-reserved work."""
        positive_integer(actual, "actual", allow_zero=True)
        if resource not in LIMITS:
            raise ValueError("Unknown prior-usage resource")
        if any(not isinstance(value, str) or not value.strip() for value in (usage_id, receipt)):
            raise ValueError("Stable prior usage identity and evidence receipt required")
        with self.transaction() as connection:
            if resource == "modal_micro_usd" and connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='modal_reconciliation_rows'").fetchone():
                if connection.execute("SELECT 1 FROM modal_reconciliation_rows WHERE id=?", (usage_id,)).fetchone():
                    raise LedgerConflict("Provider row belongs to reconciled reserved work, not prior usage")
            previous = connection.execute("SELECT * FROM prior_usage WHERE id=?", (usage_id,)).fetchone()
            if previous and previous["resource"] != resource:
                raise LedgerConflict("Prior usage identity reused for another resource")
            if previous and previous["latest_actual"] == actual and previous["receipt"] == receipt:
                return dict(previous)
            accounted = max(actual, previous["actual"] if previous else 0)
            connection.execute("INSERT INTO prior_usage VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                               "actual=excluded.actual,latest_actual=excluded.latest_actual,receipt=excluded.receipt",
                               (usage_id, resource, accounted, actual, receipt))
            total, normal = self._usage(connection, resource)
            limits = connection.execute("SELECT * FROM limits WHERE resource=?", (resource,)).fetchone()
            exceeded = ((total > limits["total"] or normal > limits["normal"])
                        and not (resource == 'litellm_tokens' and self._tokens_disabled(connection)))
            if exceeded:
                connection.execute("UPDATE campaign SET frozen=1,reason=?",
                                   ("Imported prior provider usage exceeds campaign allowance",))
            self._event(connection, "prior_usage_imported", {
                "id": usage_id, "resource": resource, "reported_actual": actual, "accounted_actual": accounted,
                "previous_accounted": previous["actual"] if previous else 0, "receipt": receipt,
                "overrun": exceeded, "downward_revision_retained": actual < accounted})
            return dict(connection.execute("SELECT * FROM prior_usage WHERE id=?", (usage_id,)).fetchone())

    def freeze(self, reason):
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("Freeze reason is required")
        with self.transaction() as connection:
            connection.execute("UPDATE campaign SET frozen=1,reason=?", (reason,))
            self._event(connection, "frozen", {"reason": reason})

    def snapshot(self):
        with self.transaction() as connection:
            campaign = dict(connection.execute("SELECT * FROM campaign").fetchone())
            resources = {}
            for limits in connection.execute("SELECT * FROM limits").fetchall():
                total, normal = self._usage(connection, limits["resource"])
                resources[limits["resource"]] = {
                    "committed": total, "normal_committed": normal,
                    "total_limit": limits["total"], "normal_limit": limits["normal"],
                    "remaining": max(0, limits["total"] - total),
                    "normal_remaining": max(0, min(limits["normal"] - normal, limits["total"] - total)),
                }
                if limits["resource"] == "litellm_tokens" and self._tokens_disabled(connection):
                    resources[limits["resource"]].update(
                        enforced=False, total_limit=None, normal_limit=None, remaining=None, normal_remaining=None)
            reservations = [dict(row) for row in connection.execute("SELECT * FROM reservations ORDER BY id")]
            reconciled = []
            if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='modal_reconciliation_groups'").fetchone():
                reconciled = [dict(row) for row in connection.execute(
                    "SELECT id,floor,observed,excess FROM modal_reconciliation_groups ORDER BY id")]
            return {"campaign": campaign, "resources": resources, "reservations": reservations,
                    "reconciled_modal_groups": reconciled,
                    "prior_usage": self._prior_rows(connection),
                    "expired_held": [row["id"] for row in reservations
                                     if row["state"] == "held" and row["expires_at"] <= int(time.time())],
                    "event_count": connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True)
    parser.add_argument("operation", choices=["initialize", "reserve", "settle", "freeze", "snapshot"])
    parser.add_argument("--json", default="{}", help="Operation arguments as a JSON object")
    args = parser.parse_args()
    ledger = CampaignLedger(args.db)
    result = getattr(ledger, args.operation)(**json.loads(args.json))
    print(json.dumps(result if result is not None else {"ok": True}, sort_keys=True))


if __name__ == "__main__":
    main()
