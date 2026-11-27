# 0001. Postgres as the single store, with analytics in SQL views

## Context

Data comes from three sources with different shapes (Hevy workouts and sets, Strava activities, markdown log tables). Reports, verification and the coach all need the same numbers: effective sets, tonnage, weekly volume per muscle, best set per exercise.

## Decision

Store everything in one Postgres schema (plain SQL migrations in `supabase/migrations/`, any Postgres 13+) and define the metrics once as views: `v_session_summary`, `v_weekly_volume_by_muscle`, `v_exercise_progression`, `v_weekly_cardio`. The report reads the session summary, progression and cardio views instead of re-implementing those formulas; `verify.py` recomputes the weekly volume on purpose, as an independent check.

## Alternatives considered

- **SQLite file.** Simpler to ship, but weaker for concurrent scheduled jobs and for sharing one database between the jobs and the tools that read it.
- **Pandas over JSON exports.** Fast to start, but every consumer would carry its own copy of the formulas.
- **A BI tool computing the metrics.** Moves the definitions out of version control.

## Consequences

- Metric definitions are versioned, reviewed and testable in one place. Some queries (`load_steps.py`, parts of `report.py`) still read the tables directly; moving them to views is a possible follow-up.
- `verify.py` can recompute a view independently and compare.
- Supabase is optional: the migrations run on any Postgres, and `init_db.py` applies them without the Supabase CLI.
- Changing a metric means a new migration, not an edit in several scripts.
