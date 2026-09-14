# Authenticated LiteLLM research settlement

Date: September 14, 2026 UTC.

This is live provider evidence for the controller-local research relay. It is not a
GameWorld benchmark result and incurred no Modal spend.

## Dedicated key

- Endpoint: `https://litellm-public.tail204509.ts.net`.
- Key alias: `gameworld-autoresearch-20260914`.
- Allowed models: Astra, Sol, Terra and Luna aliases used by the Pi profile.
- Expiry: September 21, 2026 at 11:44:24 UTC.
- Secret custody: external mode-0600 file under the local campaign state directory;
  no key bytes are stored in this repository or exposed to Pi.
- `scripts/litellm_research_key.py verify` authenticated the model allowlist with
  the virtual key through `/v1/models`, then authenticated alias, expiry, concurrency
  and unblocked policy with the admin key through `/key/list?key_alias=...`.

## Relay probe

One streaming Luna request traversed `ResearchGateway` with separate local,
virtual-key and admin credentials. The relay buffered the complete SSE response,
observed 1,634 prompt plus 5 completion tokens, joined response call ID
`826b0e05-ef80-47d5-bbf5-7f29c09ac2ea` to the dedicated-key row returned by
authenticated `/spend/logs/v2`, and verified the same 1,639-token total.

Ledger evidence:

- Dispatch: `litellm:82c927d0-8244-45c9-8bf3-b0a6924b66cf`.
- Reservation: 433,152 tokens, covering the final attempt and two configured retry
  envelopes.
- Provider-reported retries: 0.
- Settled actual: 1,639 tokens.
- Receipt: `litellm-spend:27767f1b5b2388ea4191d7a1cd953a54fbcc99ddb336ff05f5ba948e436c152a`.
- Final state: settled; campaign remained unfrozen.

This proves the no-retry live path and the call-ID/spend-log join. Offline failure
injection covers delayed/missing logs, duplicate rows, cross-key rows, response
usage mismatch, provider retry counts, failed-attempt rows and conservative hidden
retry retention. A naturally occurring live retry was not forced.
