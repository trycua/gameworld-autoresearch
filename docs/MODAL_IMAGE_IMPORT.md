# Supervised training-image import

`TrainingImageImport` maps the verified, digest-pinned GHCR training image into
the contributor-authorized Modal app. It uses no registry secret, added Python,
GPU request, user Dockerfile command, volume or force-rebuild option. Modal's own
registry setup can modify the imported base, so runtime integrity/version checks
are still required before using the resulting image for training.

Before calling Modal, it verifies the trusted CI provenance hash, exact public
repository/digest and source revision, checks pinned app/environment identity,
and atomically records a $25 normal-budget hold plus submission intent in the
canonical campaign ledger. Only one unresolved import is allowed. The returned
Modal image ID is durably recorded before a local receipt is emitted. Replaying
a completed import returns the same ID without rebuilding or refunding its hold.

A failed, interrupted or timed-out call retains the entire hold and prohibits
automatic retries, including after process restart. The client wait is 900
seconds; cancellation of that wait does **not** prove server-side build
termination. Unknown builds require explicit provider reconciliation before
another import. The hold expires after one hour but is not refunded; the ledger
then refuses further work until reconciliation. This does not reset campaign
limits or use the shutdown reserve.

The $25 hold is a conservative supervised-probe allocation, **not an independently
verified all-in import maximum**. The inspected SDK has no public per-import
CPU/memory/timeout controls for `Image.from_registry`. The official pricing and
budget pages did not establish an image-import-specific maximum. No free-build
assumption is made. Retain the hold until authoritative app billing is reconciled;
do not promote this probe into unattended image production or claim complete
$2,000 all-in enforcement from the reservation alone.

The CLI `scripts/modal_image_import.py` requires an existing campaign ledger,
trusted app scope/provenance hash and explicit `--supervised-probe`. That switch
records operator intent, not an authentication boundary. Researchers must not
have access to this command's credentials or trusted state. The importer is not
a general training launcher and creates no GPU sandbox.

Checks: `python -m scripts.modal_image_import_check` verifies durable reservations,
budget refusal before the build, immutable provenance/digest inputs, scope
validation, completed replay and ambiguous-response restart behavior.

## Live evidence

The timestamp-enabled image was imported successfully in 152.77 seconds as
`im-DDd0N6Q0E4OoWi4ZH3iPhP`, backed by registry digest
`sha256:0a55fc62e69d7a14ba9bfac9f79ba190bb1886021d27fab3b599357358533f03`.
A separate `ImageFromId` API read confirmed it. Completed replay returned the
same ID with the build method disabled, and the $25 hold remains retained.
Evidence: `results/runs/modal-image-import-20260914/` and
`results/runs/qwen-training-image-6a1309c/`.

The imported image subsequently passed source/cache checks and a real pretrained
L40S LoRA update/reload; see `docs/results/2026-09-14-qwen-pretrained-gpu.md`.
Modal 1.5.5 does not support arbitrary `Image.hydrate()` calls: use its public
lazy `Image.from_id` constructor with Sandbox creation, or the pinned SDK's
read-only `ImageFromId` RPC for a standalone identity check. No extra build was
issued to perform verification.
