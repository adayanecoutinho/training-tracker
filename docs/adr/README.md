# Architecture Decision Records

Short records of the decisions behind the current design. Format: Context / Decision / Alternatives considered / Consequences.

| ADR | Decision |
|---|---|
| [0001](0001-postgres-with-views.md) | Postgres as the single store, with analytics in SQL views |
| [0002](0002-idempotent-incremental-sync.md) | Idempotent incremental sync with an event cursor |
| [0003](0003-canonical-exercise-aliases.md) | Canonical exercise names through a human-reviewed alias file |
| [0004](0004-guarded-coach-prompt.md) | The coach is a guarded prompt with read-only access |
| [0005](0005-scheduled-job-external-health-check.md) | Scheduled job monitored by an external health check |
