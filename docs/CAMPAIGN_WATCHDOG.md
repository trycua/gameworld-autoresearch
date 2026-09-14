# Independent cleanup watchdog

The watchdog is cleanup-only: it cannot admit work, create claims/sandboxes,
run training, settle unknown charges, or reset the campaign deadline. Run it in
a separate supervised process on the same trusted host and local filesystem as
the existing controller database. It does not initialize a new campaign.

```bash
python -m fps_bench.campaign_watchdog \
  --database "$CAMPAIGN_DATABASE" \
  --contract "$CONTRACT_PATH" --contract-sha256 "$CONTRACT_SHA256" \
  --fleet-receipts "$EXISTING_FLEET_RECEIPT_DIRECTORY"
```

Use the same receipt directory as the Fleet controller, preserving recorded
claim ownership. The optional Fleet adapter currently supports only admitted
`warm-driver-probe` jobs. Modal training cleanup uses persisted launch identity
and provider tags. Use the approved Fleet/Modal credentials in this trusted
process, never in researcher environments. Protect its database and credentials
from candidate workers. Dependencies are the existing Fleet and Modal SDKs.

Every 15 seconds by default, the process checks the persisted campaign stop,
budget freeze, campaign deadline and job deadlines. It cancels jobs proven never
dispatched and terminates expired/stopped provider work. It does not terminate
healthy work or race artifact export merely because results are available.
Each cleanup has a 210-second bound and runs independently of other due jobs.
Unresolved cleanup is audited and retried on later passes. A local advisory lock
prevents duplicate watchdog processes for the same database path.

`--once` performs a bounded recovery pass, exits nonzero if any cleanup is
unresolved, and can be used after a controller crash. Modal termination retains
the budget reservation and training slot until authoritative billing settlement.
A missing ambiguous create is not refunded or recreated. Unknown job kinds are
reported as unresolved, not silently considered cleaned. No scale-to-zero
observation runs; that check was waived by the user.

## Evidence and limits

`scripts/campaign_watchdog_check.py` exercises deadline cancellation, stop,
restart, lost create acknowledgement, absent ambiguous create, ownership
mismatch, cleanup failure/retry, unsupported jobs, and concurrent timeout
isolation. A credential-free subprocess actually opens and cleans an expired
undispatched job from the durable database and verifies replay after restart.
Provider operations in these tests are fake; they do not prove live GPU cleanup.

This is not yet a deployed supervisor or an independent host-failure recovery
system. It cannot access the database after host loss; provider TTL remains the
last backstop. It does not detect a stalled controller before persisted deadlines.
Research-process and evaluation-serving cleanup adapters, out-of-band alerts,
real GPU timeout/termination and live all-in billing reconciliation remain launch
gates. Emergency termination may lose unexported results; avoiding continued
resource consumption takes priority after a stop or expiry.
