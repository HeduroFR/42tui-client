# API compatibility

The client talks HTTP to the configured `FT_TUI_API_URL` origin, defaulting to
`https://oauth.42wip.in`. It never needs server source or server OAuth secrets.
The existing protocol uses `/v1` data routes, device pairing/session routes,
DPoP proofs, account-scoped payloads, pagination, idempotency keys for writes,
and authenticated event streams. Repository separation changes none of these.

Client package 0.3.0 and API major v1 are independent version identifiers.
The backend owns the canonical OpenAPI documents. Publish a separately reviewed,
implementation-free contract snapshot when sharing those documents publicly is
approved. This client preview contains no server OpenAPI files or internal plans.
Its typed decoders and synthetic HTTP mocks describe its current expectations;
they are partial test coverage, not a complete formal API specification.

For v1 changes, keep required fields, types, enum meanings, account/scope checks,
DPoP behavior, error distinctions and stale/pending data semantics compatible.
Add optional capabilities conservatively: some client decoders reject extra enum
values. Removing or reinterpreting required behavior requires a new API major
and an overlap period. Do not require all installed clients to upgrade together.

Before either side releases, test the candidate with the current supported peer
and the oldest peer still supported. Record exact client version and backend
commit/image digest. Establish that support window before production cutover;
no minimum backend version or compatibility handshake is currently enforced.
Roll out additive server/schema changes before clients that consume them; keep
old routes available for rollback. Missing features must fail predictably without
clearing local notes, projects or cached account data.

The fuzzy-search fixture and cluster layout are pinned shared behavior snapshots.
The migration validator compares snapshot hashes, and each repository tests its
own implementation against the pinned fixture. Changing snapshots requires
coordinated review rather than an implicit sibling import.

## Cross-repository verification and failed deployments

The private backend repository owns a manual compatibility workflow. A maintainer
supplies exact candidate client/backend commit SHAs, an explicitly supported oldest
client SHA and the current healthy backend SHA. It tests the candidate pair,
oldest-client/new-backend and new-client/current-backend with the existing synthetic
friend-preview HTTP scenario. Other feature contracts require their own cases;
this initial scenario does not cover the entire API. The client CI needs no private
backend credentials and no privileged workflow is triggered by public PR code.

Client auto-update helps shorten the support window, but users can be offline,
disable updates, defer exit or encounter an installation failure. Keep an explicit
supported baseline and graceful unavailable-feature behavior rather than assuming
all installations update with a server deployment. Versions remain independent.

A passing pair receipt is not deployment proof. Before a dependent client release,
a trusted release process must verify a healthy production backend at the exact
tested commit/image digest, including functional checks beyond liveness. Backend
`compatibility/coordination.py` can validate trusted test/deployment JSON evidence
and reject failed, stale or mismatched deployments. This checker does not deploy,
query production, sign attestations or publish packages; no active release gate is
wired yet. Release the immutable client artifact from the tested commit/version.

If the backend deployment fails, block the dependent client release and keep or
restore the previous healthy compatible image. An unrelated client-only fix can
release independently. Use backward-compatible database migrations so both images
can run during transition; reverting the image does not undo migrations. Delay
schema removal until the support window closes. After a client is published, do
not rely on recalling it or forcing every installed copy to update immediately.
