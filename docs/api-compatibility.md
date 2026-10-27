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
