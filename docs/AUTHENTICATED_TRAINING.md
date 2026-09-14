# Controller-authenticated training data

`TrainingRegistry` binds data to the canonical controller database. A caller's
train seed list and dataset hash alone no longer authorize a production GPU
launch. Modal preparation, start, staging and worker dispatch require registry
authentication, including a fresh verification of the custody bytes.

The trusted rollout collector must first verify provider identity, frozen source
and driver/model identity, export artifacts, and record a completed evaluation
job assigned to `train`. Its controller result artifact hash must be the SHA-256
of the canonical train episode receipt, not an unverified worker claim. The
registry checks this hash against the durable acknowledged job, assignment and
registered candidate before accepting an episode. It additionally verifies the
complete trajectory and screenshot inventory with the train-only exporter.

`register_episode(job_id, root, receipt)` preserves an immutable custody binding.
`export(sorted_job_ids, output)` produces the dataset from those registered
receipts and journals its manifest, hash, custody root and source job IDs in the
same database. `authenticate(training_job_id)` rechecks the dataset, receipts,
source candidate and train assignments. Development/confirmation/sealed episodes
cannot enter the train-only path. Training receives screenshot/action examples,
not evaluator state or reward fields in the sample messages.

The registry is a trusted-host boundary, not a signature scheme or OS sandbox.
A process that can write the canonical SQLite database can impersonate the
controller. Candidate code must not receive that database, provider credentials,
private evaluator files, or write access to custody. Read-only file modes do not
isolate mutually untrusted processes running under the same user.

No frozen evaluator source is changed. Legacy historical compatibility probes
remain historical evidence, not authenticated campaign training examples.

## Checks and remaining integration

`python -m scripts.training_registry_check` exercises the real registry with
synthetic, frozen-contract trajectory fixtures: acknowledged job/result binding,
candidate identity, train-only data, immutable custody, missing provenance,
reopen, tampering, and refusal before provider creation. Existing Modal lifecycle
and transport unit tests explicitly mock the registry boundary to retain their
focused fake-provider coverage; they do not prove live rollout authenticity.

The production rollout collector still needs to create these receipts through an
authenticated provider lifecycle. Independent evaluator replay, composite Fleet
and serving cleanup/recovery, campaign-wide cost coverage and the integrated live
train-to-evaluation campaign remain launch gates. This module is not a launch
command and does not initialize the canonical campaign's six-hour deadline.
