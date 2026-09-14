"""Controller-side imports of historical Modal app-hour costs, never job settlement."""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import re

from fps_bench.evaluation_contract import canonical, digest
from fps_bench.campaign_ledger import LedgerConflict


def usd_to_micro(value):
    if not isinstance(value, str):
        raise ValueError("Modal costs must preserve provider decimal strings")
    try:
        amount = Decimal(value)
    except InvalidOperation as error:
        raise ValueError("Invalid provider cost") from error
    if not amount.is_finite() or amount < 0 or amount > Decimal("1000000000"):
        raise ValueError("Invalid provider cost")
    return int((amount * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def utc_hour(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed.utcoffset().total_seconds() != 0 or parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError("Expected a complete UTC hour boundary")
    return parsed


def normalize_report(rows, scope):
    required = {"workspace", "environment", "object_ids", "start", "end"}
    if not isinstance(scope, dict) or set(scope) != required:
        raise ValueError("Explicit immutable historical billing scope required")
    if not all(isinstance(scope[key], str) and scope[key] for key in ("workspace", "environment")):
        raise ValueError("Workspace and environment identity required")
    objects = scope["object_ids"]
    if (not isinstance(objects, list) or not objects or len(set(objects)) != len(objects)
            or any(not isinstance(item, str) or not re.fullmatch(r"ap-[A-Za-z0-9]+", item) for item in objects)):
        raise ValueError("Explicit unique Modal app IDs required")
    start, end = utc_hour(scope["start"]), utc_hour(scope["end"])
    if start >= end or end > datetime.now(timezone.utc):
        raise ValueError("Only completed historical hours can be imported")
    if not isinstance(rows, list):
        raise ValueError("Expected provider report rows")
    normalized, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid provider report row")
        if row.get("object_id") not in objects:
            continue
        if row.get("environment") != scope["environment"]:
            raise ValueError("Known campaign app appeared in a different environment")
        stamp = utc_hour(row["interval_start"])
        if not start <= stamp < end:
            continue
        identity = [scope["workspace"], scope["environment"], row["object_id"], stamp.isoformat()]
        key = "modal-app-hour:" + digest(canonical(identity))
        if key in seen:
            raise ValueError("Duplicate provider app/hour row; resource breakdowns are not accepted")
        seen.add(key)
        item = {"id": key, "object_id": row["object_id"], "interval_start": stamp.isoformat(),
                "cost_usd": row["cost"], "micro_usd": usd_to_micro(row["cost"])}
        item["receipt"] = "modal-billing-row:" + digest(canonical({"identity": identity, "cost": row["cost"]}))
        normalized.append(item)
    return sorted(normalized, key=lambda item: item["id"])


def import_report(ledger, rows, scope):
    normalized = normalize_report(rows, scope)
    with ledger.transaction() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS modal_prior_scope (singleton INTEGER PRIMARY KEY CHECK(singleton=1), specification TEXT NOT NULL)")
        stored = connection.execute("SELECT specification FROM modal_prior_scope").fetchone()
        specification = canonical(scope).decode()
        if stored and stored["specification"] != specification:
            raise LedgerConflict("Historical Modal scope is immutable; do not overlap it with live settlements")
        if not stored:
            if connection.execute("SELECT 1 FROM reservations WHERE resource='modal_micro_usd' LIMIT 1").fetchone():
                raise LedgerConflict("Import history before admitting Modal work to prevent duplicate accounting")
            connection.execute("INSERT INTO modal_prior_scope VALUES (1,?)", (specification,))
    for item in normalized:
        ledger.record_prior_usage(item["id"], "modal_micro_usd", item["micro_usd"], item["receipt"])
    return {"scope": scope, "scope_sha256": digest(canonical(scope)), "rows": normalized,
            "reported_micro_usd": sum(item["micro_usd"] for item in normalized),
            "snapshot": ledger.snapshot(),
            "limitations": ["Historical app-hour costs only; not live job settlement",
                            "Provider reports may arrive late or be revised; missing rows are not proof of zero",
                            "No negative refunds; each interval retains its greatest observed amount",
                            "Scope excludes other objects, storage and unfinished hours unless separately accounted"]}
