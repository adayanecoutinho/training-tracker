# 0002. Idempotent incremental sync with an event cursor

## Context

The sync runs unattended on a schedule. It can be interrupted, re-run by hand or run twice. Workouts can be edited or deleted in Hevy after they were imported.

## Decision

- Every write is an upsert on a natural key (`hevy_id`, `strava_id`, `(workout_id, exercise_order, set_index)`, deterministic `uuid5` for log sessions).
- Hevy changes come from `/v1/workouts/events`, starting at a cursor stored in `sync_state`. `updated` events upsert the workout and prune vanished sets; `deleted` events set `deleted_at` (soft delete).
- The saved cursor is the time taken before downloading, written in the same transaction as the changes. The Strava cursor advances only after all pages succeed.
- Without a cursor, `sync.py` imports the local backup first.

## Alternatives considered

- **Full reload every run.** Simple, but slow, heavy on rate limits, and it would lose enrichments (RIR and notes from the logs).
- **Fetch by an `updated_at` window.** Would miss deletions, which only the events endpoint reports.
- **Hard delete.** Loses history; soft delete keeps it and the views filter it out.

## Consequences

- Running any import twice leaves the counts unchanged.
- A crash causes some events to be read again, never a gap.
- Analytics must always filter `deleted_at IS NULL` (the views do).
