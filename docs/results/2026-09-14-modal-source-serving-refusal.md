# Modal source-serving pre-submission refusal

The first controller-owned source-serving vertical slice was admitted as
`baseline-serving-v1` with a `$10` ledger hold, but Modal rejected the request
before creating a Sandbox:

```text
Cannot specify open ports when `block_network` is enabled
```

The launch requested encrypted port 8000 and `block_network=True`. A fresh
provider lookup for the immutable Sandbox name
`gw-serve-9f364e8c86a7be9d86ec` returned no resource. The controller then closed
the unacknowledged dispatch with receipt
`provider-refused:60496a6912bbee4151cfcfcfe642305e7d478862c99c824bff56f7f4e9bee888`
and settled the reservation at zero. Campaign commitment returned to
`$206.013141`; no GPU Sandbox was created or retried.

Root fix `7f25380` uses `outbound_cidr_allowlist=[]`, the network-isolated pattern
already proven by the frozen baseline, while retaining encrypted port 8000. It
also journals submission errors and permits zero-cost closure only for an exact
known provider refusal after a named-Sandbox absence check. Other create errors
remain ambiguous and cannot be retried automatically.

Evidence is under
`/home/node/.local/state/gameworld-autoresearch/campaigns/gameworld-joint-20260913/vertical-slices/baseline-serving-v1/`.
The corrected live slice remains required after the rebuilt image and evaluation
contract are pinned.
