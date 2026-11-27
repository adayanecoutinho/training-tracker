# Architecture

## Components

| Component | Files | Role |
|---|---|---|
| Source clients | `hevy.py`, `strava_client.py`, `strava_auth.py`, `obsidian_parser.py` | Read-only access to the Hevy API, the Strava API (OAuth on loopback, auto refresh, rate-limit aware) and the Obsidian markdown logs. |
| Configuration | `env.py`, `db.py`, `history_config.py` | Load `.env` with the stdlib; connect to Postgres through `DATABASE_URL`; define the start of comparable history (`TRAINING_HISTORY_START`). |
| Importers | `dump.py`, `import_hevy.py`, `sync.py`, `sync_strava.py`, `import_obsidian.py` | Full backup, incremental sync and log import, all idempotent. |
| Exercise catalogue | `canonical_aliases.py`, `generate_aliases.py`, `exercise_aliases.csv`, `apply_aliases.py` | Map every source name to one canonical exercise after human review. |
| Storage and analytics | `supabase/migrations/*.sql`, `init_db.py` | Tables plus the views `v_session_summary`, `v_weekly_volume_by_muscle`, `v_exercise_progression`, `v_weekly_cardio`. |
| Verification | `verify.py` | Recompute view results independently and compare. |
| Reports | `report.py`, `load_steps.py` | Descriptive weekly report and observed load steps per exercise. No recommendations. |
| Scheduling | `job.py`, `Dockerfile` | Run the `sync` and `relatorio` jobs and ping an external health check. |
| Coach | `agents/coach.md` | Prompt for an AI coach that reads the report and the methodology notes. |

## Data flow

1. **Hevy.** `dump.py` saves the full history to `data/raw/*.json`. `import_hevy.py` loads it in one transaction. Afterwards, `sync.py` reads `/v1/workouts/events` from the cursor in `sync_state` (`hevy_events_since`), applies `updated` events as upserts and `deleted` events as soft deletes (`deleted_at`), oldest first.
2. **Strava.** `sync_strava.py` pages activities from the last stored start time (one second of overlap), skips strength sessions already recorded by Hevy, stores only summary fields (no maps, coordinates or location) and advances `strava_last_start` only after all pages succeed.
3. **Obsidian.** `import_obsidian.py` parses the markdown log tables. On a date that already has a Hevy workout it only fills missing RIR and notes on matching sets; otherwise it creates an `obsidian` workout with a deterministic id.
4. **Catalogue.** `apply_aliases.py` applies the reviewed CSV and merges exercises that share a canonical name, re-pointing their sets.
5. **Analytics.** Views compute effective sets (everything except warm-ups), tonnage, average RPE, weekly volume per muscle (primary 1, each distinct secondary 0.5), best set by Epley e1RM and weekly cardio. Soft-deleted workouts are excluded.
6. **Report.** `report.py` reads `v_session_summary`, `v_exercise_progression` and `v_weekly_cardio` (plus a few direct queries on the tables), `load_steps.py` aggregates `sets` directly, and both write markdown to `reports/`.
7. **Coach.** The coach reads the latest report and the methodology notes and writes its review to an inbox file.

## Idempotency and deduplication

- **Natural keys everywhere.** `workouts.hevy_id`, `cardio_sessions.strava_id`, `sets(workout_id, exercise_order, set_index)`, `exercise_hevy_templates.template_id`, `body_metrics.date`. Every write is `INSERT ... ON CONFLICT DO UPDATE`.
- **Deterministic ids for log sessions.** Obsidian sessions use `uuid5("obsidian:<date>:<title>")`, so re-importing hits the same row.
- **Removed positions are pruned.** After an upsert, set positions that no longer exist in the source are deleted; unchanged sets keep their ids.
- **Cross-source merge, not copy.** A log row for a day that Hevy already has never creates a second workout; it only enriches the Hevy sets, and never overwrites Hevy loads or reps.
- **Hevy copies in Strava are skipped**, so a strength session never counts twice as cardio.
- **Cursors move last.** The Hevy cursor is the timestamp taken before downloading events, written in the same transaction as the changes; the Strava cursor moves only after all pages are processed. A crash means re-reading, never skipping.

## Verification

`verify.py` is the check that the analytics can be trusted:

- for sample workouts, effective sets and tonnage from `v_session_summary` must equal the values recomputed from the raw JSON backup;
- the whole `v_weekly_volume_by_muscle` must equal an independent aggregation of all sets in Python (week start, primary 1, distinct secondary 0.5);
- table counts are printed so two databases can be compared side by side.

When the data moved between databases, per-table counts were compared between source and target: 152 workouts, 3,031 sets, 488 exercises and 101 cardio sessions, all matching.

The unit tests (`test_*.py`) cover the scheduled job, the history cut-off, load-step rendering, the Strava client and the fictional examples, with no network and no database.

## Scheduled job and monitoring

`job.py sync` runs `sync.py` then `sync_strava.py`; `job.py relatorio` runs `report.py --weeks 8` then `load_steps.py`. Each job pings `<url>/start`, then `<url>` on success or `<url>/fail` with only the step name and exit code. The URL comes from the environment and is never printed; a failed ping never fails the job; a failed step stops the job with its exit code. A missed or failed run is therefore visible from outside, through the health-check service.

## Coach guardrails

The coach is a prompt, not code with write access. `agents/coach.md` fixes:

- **No diagnosis.** It does not give medical or nutritional advice; anything outside training is referred to a professional.
- **Cites its sources.** Every rule comes from a named methodology note and every number from the report; contradictions between sources are stated, not resolved silently.
- **No rule changes without confirmation.** It may propose a change with the reason; the current rule stays in force until the person confirms.
- **Read-only access to notes.** Methodology notes and reports are read-only for the coach.
- **Writes only to an inbox.** One file per delivery, stating where the data came from. It never edits, moves or deletes anything else, and never writes to the database or the repository.
