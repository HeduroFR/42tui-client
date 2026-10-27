# Client architecture

The client uses feature modules with explicit service, state, port, adapter and
presentation boundaries. The app shell composes dependencies and coordinates
lifecycle/routing. Screens, shortcuts, HTTP behavior and local data formats are
preserved. Package version remains 0.3.0; separation and internal refactoring do
not publish a release.

## Current ownership

| Module | Responsibility |
|---|---|
| `features/accounts/service.py`, `ports.py` | Independent account/cursus reads without UI or storage dependencies; profile capability stays optional |
| `features/accounts/state.py` | Account identity and presentation state; shell attributes forward to this single owner |
| `features/accounts/views/connection.py` | Existing Textual device-pairing/disconnection flow |
| `features/catalog/models.py`, `preferences.py`, `ports.py` | Catalog DTO validation, selection rules and narrow provider/repository contracts |
| `features/catalog/service.py` | Headless paginated synchronization, context fences and complete snapshot staging |
| `features/catalog/adapters/` | Existing persisted projections and SQLite session/transaction lifetimes |
| `features/catalog/state.py` | Catalog loading/navigation state |
| `features/catalog/views/controller.py` | Textual workers, retry timers, notifications and widget updates; no database sessions |
| `app/bootstrap.py` | Production construction of feature services and adapters; constructors accept explicit service injection |
| `app/read_cache.py` | Shell-context conversion and authorization-loss/persistence callbacks |
| `features/profiles/` | Cached profile/goals projections, credential-bound persistence, polling decisions and state |
| `features/dashboard/` | Portable home view models, read-only local activity adapter and Textual dashboard rendering |
| `shared/context.py`, `shared/read_cache.py` | Immutable account read identity, origin normalization and bounded reusable read coordination |
| `shared/portraits.py` | Image byte-size policy shared by download and rendering |
| `infrastructure/security/keychain.py` | Unchanged OS credential-store adapter and identifiers |

Feature services/models/state/ports do not import Textual, SQLAlchemy, httpx,
concrete infrastructure or the app shell. Adapters own I/O. Views render service
results and route input. `tests/test_architecture_boundaries.py` enforces these
rules for migrated feature cores and the catalog presentation adapter.

Account read identity includes normalized backend origin, account ID, generation
and provider identity. Catalog operations also retain scope/catalog generations
and snapshot IDs. Late or superseded network results cannot replace active data.
The SQLite adapter stages all catalog scans in one transaction; partial or mixed
snapshots leave the previous complete catalog intact. Sessions never cross await
or thread boundaries. Persistence remains on the UI loop, as before.

## Shared code and feature ownership

Feature implementations, DTOs and views live under `features/`.
The former `services/`, `cluster_map/` and `slots/` packages and feature aliases
in `api/` and `ui/` have been removed. Imports and mock patch targets must use
the owning feature module. Old Python import paths are no longer supported;
the CLI commands, HTTP contract, database schema and credential identifiers
are unchanged.

`api/` contains the common HTTP/OAuth transport and provider contract.
`ui/` contains the Textual app shell, shared widgets, onboarding, commands,
navigation and styles. `app/` composes services and adapters; `db/`, `config/`,
`infrastructure/` and `shared/` contain cross-feature infrastructure and policies.
Fuzzy matching belongs to `shared/fuzzy_search.py`. Project Git inspection,
settings, technical details and tester views belong to projects; catalog browser,
classification and evidence rendering belong to catalog. Cluster geometry loads
`features/cluster_map/layout.json` through `importlib.resources`.

Textual presentation retains mixin composition and existing event routes.
Local catalog/project readers still return eager ORM projections where current
views depend on them, and the catalog browser retains its local preference
sessions. These are explicit integration boundaries, not compatibility facades.

## Tests

Use Python >=3.12 with the project installed in an isolated editable environment:

```sh
python -m pip install -r requirements-dev.txt
python release/regression_scopes.py --check
python release/regression_scopes.py --scope accounts
python release/regression_scopes.py --scope catalog-curriculum
python -m unittest discover -s tests
```

Do not export a source-tree PYTHONPATH when running real installer lifecycle
tests: it can leak into a subprocess's temporary installed CLI and shadow its
candidate wheel. Editable installation provides the correct import behavior.
Use disposable databases and synthetic HTTP fixtures; never test against real
user credentials or browser/session data.

## Dashboard and profile stage

ProfileService owns current profile/goals snapshots and the 900-second fresh /
30-second pending-or-stale polling decision. The Textual dashboard still schedules
workers and timers; it does not open database sessions or decide persistence.
Profile cache fields, credential digests and goal keys are unchanged. Pending or
failed reads preserve a scoped final observation, and superseded contexts never
persist their results. Account startup hydrates the same cached first frame.

DashboardService composes portable project, profile, goal and local-activity read
models. Its temporary SQLite worklog reader supplies notes, heartbeat aggregation,
tracked time and activity ordering without passing ORM rows into the view. Folder
checks are a capability supplied by bootstrap. This bridge will be replaced behind
the same port when worklog ownership migrates. The dashboard view keeps selectors,
rendering, portrait cache and Textual event handling; an explicit render revision
prevents old refreshes from appending obsolete note entries.

The later workflow stage owns profile detail screens and portrait transport.
The shared HTTP provider remains a compatibility transport boundary. The shared app
still coordinates other features and their old mixins.

## Projects and worklog stage

Worklog owns portable note/timer/heartbeat outcomes, note editor state, its SQLite
repository, the unchanged accounting implementation and local activity read
adapter. Notes CRUD, timer controls, project note links and heartbeat CLI ingress
now use WorklogService. Accounting retains its naive UTC convention, 120-second
idle cutoff and transactional credit rules. Sidebar refreshes reject an obsolete
load, and saving a note retains its identity for subsequent edits.

Projects owns safe Git checkout, navigation and tester adapters, ProjectService,
its settings transaction adapter, and setup/navigation/details views. Changing
a checkout path invalidates path-bound subject metadata exactly as before.
Subject refresh and registration/team/activity UI belong to their project workflow modules.
Existing shared project ORM projections remain transitional; not all project
persistence has been converted to portable domain models. The settings adapter returns the
existing eager-loaded project projection so current view callers retain behavior.

The worklog-owned activity adapter supplies the dashboard with local activity queries. Filesystem,
subprocess and Docker work stays in adapters or existing terminal presentation;
the refactor does not run a user's real checkout setup or testers during tests.

## Friends, clubs and social stage

Friends owns its response validators, pure comparison/ranking rules, headless
summary/detail/batch/search operations and SQLite observation repository. Portable
confirmed memberships leave the adapter; friends views no longer open sessions.
Summary capability fallback keeps its existing 400/404 policy, and per-account,
origin, cursus and provider fences remain around cached reads and persistence.
Two concurrent profile consumers, selected-first scheduling and retry policy
remain presentation coordination. The adapter can temporarily call the shell's
configured-cursus selector while owning the session lifetime, preserving existing
harness/selection behavior during the remaining shell migration.

Clubs owns DTOs, read/poll/mutation service ports, workspace/forms, inbox and
announcement views. Social owns validated inbox models, snapshot acceptance,
confirmed-friend persistence and single-shot mutation/neighbour operations plus
inbox/poke/event views. Services check explicit current-context predicates before
dispatch and after responses; no retry or new operation UUID is introduced.
Notification/bell/DND/sound/SSE timing stays in the Textual views.

DTOs, views and storage are imported directly from their feature modules.
Ranking helper patches target `features.friends.projections`, their single owner.

The push-events view remains cross-feature presentation integration through
feature view imports; it is not a headless event bus. Sender portrait
loading and friend project preview still bridge existing profile/catalog UI.
Unsupported in-place mutation of a provider origin retains its old scope limits;
supported account/provider-generation transitions remain fenced. The common
transport remains shared across feature ports.

## Cluster map and corrections stage

Cluster map owns strict DTOs, geometry/state/experience rules, its five Textual
views, provider port and headless service. Its SQLite adapter owns membership,
configured-cursus and portrait-cache path lookups. App bootstrap injects the
service; legacy view harnesses compose the same adapter lazily. Profile reads pin
the selected user identity and retain the existing main-cursus fallback. Current
context checks fence queued reads and late responses. Issue submissions retain
the caller's UUID and single dispatch. The packaged cluster layout and terminal
portrait widget belong to `features/cluster_map/`. Profile views reuse that widget.

Corrections owns slot rules, DTOs, calendar/workspace presentation and a headless
provider service. Bootstrap constructs a stateless service; each operation receives
the currently captured provider so reconnecting does not retain an obsolete one.
Snapshot/save/delete operations check current context before queued dispatch and
after responses. Delete batches are validated before mutation; booked slots stay
protected and failures retain the completed count and original error. Optimistic
rollback, uncertain-outcome refresh, timers and status messages stay in views.
Neither feature adds automatic mutation retries. Test patch points use the
feature modules. No schema, endpoint, keychain identifier or package version changes.

## Settings and installation stage

Settings owns its workspace, primitive draft preparation, campus option selection
and account/cursus/campus preference keys. SettingsService persists through a
repository port; the SQLite adapter owns read sessions and atomic multi-key writes.
The view normalizes widget values, applies the saved state and coordinates existing
cross-feature refreshes and timers. Invalid relative roots do not persist or create
directories. Saved keys, local defaults, locale messages and shared terminal,
username, button and select components remain compatible.

Installation owns startup acknowledgement, automatic-update preference and cooldown
decisions through a local preference port. Bootstrap composes the settings SQLite
repository for this port. Its update view schedules network checks and changelog
presentation without opening sessions. Pure stable release selection and notes
parsing are separate from metadata HTTP, package-manager receipts, subprocesses,
locking and installed resource access. The existing UpdateService construction
class remains in the runtime adapter with managed installation detection. Explicit maintenance commands use the feature's separate
adapter and still avoid loading the database or TUI.

Settings, update and maintenance callers import their feature implementations.
Pure helper-global patches target their single feature model owner. The main CLI
uses installation adapters. The tiny
synthetic maintenance test wheel now includes these actual adapter package files;
it still proves update/removal against a disposable uv installation. Distribution
installers and website assets are unchanged. No real installed tool is upgraded or
removed by this refactor. App startup's remaining global preference reads and
cross-feature routing remain explicit transitional shell code.

## Remaining project and student-profile workflows

Registration owns strict registration/team DTOs, presentation decisions and
single-attempt provider operations. Its headless service preserves the reviewed
snapshot, caller operation key and captured scope. Context fences run before
queueing, inside dispatch and after responses. Views retain busy/revision/unknown
outcome state, expiry timers and context-keyed caches: selecting another project
can still populate the original cache while only the selected context renders.
Team editing keeps the existing leader, invitation, capacity and locked-state rules.

Subjects owns due-check orchestration and portable project metadata rows. SQLite
and file adapters own session lifetimes, path checks, symlink rejection, ignore
rules, bounded PDF validation, staging/replacement and metadata transactions.
SubjectMixin retains the existing timers/status messages under ProjectDetailsMixin.
Activity owns strict history/evaluation DTOs, pure presentation helpers, context
selection adapter and fenced reads through the shared cache. Existing friend
activity subclasses keep their provider hooks and cache identity.

StudentProfileService owns identity-pinned profile/attendance/project/goal reads
and portrait dispatch. Profile DTOs, pure summaries and goals validation live in
profiles; the CDN download adapter retains the existing URL allowlist, response
size limit and redirect policy. Views retain the 32-entry memory cache, section
workers, retry/poll limits, lifecycle and responsive rendering. Portrait
rendering is reused from the cluster-map portrait widget. Bootstrap injects all
workflow services; standalone view harnesses can compose the same defaults.
Private helper globals target their feature owner.

The shared API provider still implements the wire protocol behind the feature
ports; no endpoint or payload change is introduced. Local ORM projections and
global shell startup/state/routing remain explicit transitional coupling. Feature
ownership retains the shared app shell and does not authorize a release or any
real-user mutation.

## Final shell pass

AccountControllerMixin owns account connection, session-expiry handling and online
synchronization presentation. AccountShellService fences queued reads by captured
client/account/generation; its adapter owns cursus repair, memberships/directory
persistence and concrete provider construction. The shell re-exports SessionExpired
and preserves inherited method signatures. Profile persistence rejects responses
from obsolete session checks.

StartupService supplies preferences, cached cursuses, catalog projections and
branch choices through SqliteStartupRepository. The shell keeps the original
restore order: preferences, default cursus repair, profile/goals hydration,
catalog/branches, widgets and workers. Empty saved keys still count as existing
preferences, and offline owner rules remain. All former shell database sessions
now belong to adapters. Settings/project mutable state each has one owner;
StateField accessors keep legacy attribute names without duplicate state.

All callers use feature imports directly. Architecture tests enforce no direct
shell database sessions, feature core dependency rules, view persistence boundaries,
existing import targets and the absence of legacy module aliases. Remaining
extensions should respect these boundaries. This completed migration keeps the Textual mixin composition, shared wire provider
and eager local catalog projections described above.
