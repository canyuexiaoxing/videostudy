# SQLite local storage and simulated cloud MySQL implementation plan

Goal: default desktop API storage to a persistent SQLite file; keep Docker MySQL behind an authenticated cloud sync API, contacted only by explicit user actions.

Architecture: local API :18080 uses SQLite with WAL, foreign keys, bounded writer contention and SQLite-specific Flyway migrations. Cloud API :18081 uses existing Docker MySQL and a separate versioned snapshot table. Local sync sends completed course records over HTTP, never SQL credentials. Optimistic revisions reject conflicting changes. Source videos, model files, credentials and transient task tokens are excluded. Existing browser note/image storage remains local; this first database sync covers persisted backend course records, not file/blob synchronization. No paid calls or reanalysis.

- [x] Add SQLite dependency/profile/schema, default local profile; retain MySQL profile explicitly for Docker/cloud.
- [x] Write real SQLite persistence, subtitle transaction, duplicate, cascade, concurrency and reopen regression tests; adapt incompatible lock SQL.
- [x] Add authenticated cloud document storage with revision checks and safe logging. Keep existing MySQL tables/data.
- [x] Add validated course snapshot export/import and SQLite sync state; test rollback, cross-course rejection, dirty-local/conflict protection, remote outage.
- [x] Add explicit local connection/push/pull endpoints and desktop sync dialog with useful errors.
- [x] Reconfigure Docker with separate local SQLite API and simulated cloud MySQL API. Agent callbacks continue reaching local API.
- [x] Build/test both profiles and deployment: local file survives restart, MySQL sync rows verified, missing/incorrect tokens rejected, offline local API remains usable.
- [x] Package and verify desktop UI. Record boundaries, startup instructions and actual connection evidence.

No cloud login system is implemented in this branch. The development sync secret is for a private single-user setup, not a public multi-user service. Do not expose these development endpoints publicly.
