# training-tracker

A small, honest training-data pipeline: strength workouts from **Hevy**, cardio from **Strava** and older hand-written logs from **Obsidian** are merged into **Postgres**, summarized by SQL views into a weekly report, and read by an **AI coach** prompt that runs with strict guardrails.

> This is the public version of a personal project. Real training data, notes and infrastructure stay private; everything under `examples/` is fictional.

## Problem

Training history was scattered: months of workouts in a markdown table, newer ones in the Hevy app, cardio in Strava. None of it could answer simple questions ("did weekly volume per muscle actually go up?", "which loads have I really used on this machine?") and an AI assistant reading raw exports would guess, double count and invent rules.

## Solution

- **One schema, many sources.** Idempotent importers load each source into the same Postgres tables, with a natural key per record so re-running never duplicates anything.
- **Analytics in SQL views.** Session summary, weekly volume per muscle and per-exercise progression (Epley e1RM) live in versioned SQL views that the report reads and `verify.py` checks against an independent recount.
- **Human-reviewed exercise names.** The same movement has different names across apps; a reviewed alias CSV maps them to one canonical name and uncertain matches stay unmapped until a person decides.
- **Descriptive reports, guarded coach.** `report.py` only describes what happened. The coach prompt (`agents/coach.md`) reads the report and the methodology notes read-only, cites its sources, never changes a rule without confirmation and writes only to an inbox.
- **Scheduled and monitored.** `job.py` runs the sync and the weekly report and pings an external health check on start, success and failure.

## Result

- 152 workouts, 3,031 sets, 488 exercises and 101 cardio sessions migrated with matching counts.
- Idempotent sync, monitored scheduled job.

## Architecture

```mermaid
flowchart LR
    H[Hevy API<br/>strength] -->|dump.py / sync.py<br/>event cursor| ETL
    S[Strava API<br/>cardio] -->|sync_strava.py<br/>start-time cursor| ETL
    O[Obsidian logs<br/>read-only] -->|import_obsidian.py<br/>merge, no duplicates| ETL
    ETL[Idempotent ETL<br/>upserts + alias review] --> PG[(Postgres<br/>tables)]
    PG --> V[SQL views<br/>session summary, weekly volume,<br/>progression, weekly cardio]
    V --> CHK[verify.py<br/>independent recount]
    V --> R[report.py / load_steps.py<br/>weekly report]
    R --> C[AI coach prompt<br/>read-only sources, cites them,<br/>no diagnosis, writes to inbox only]
    J[job.py<br/>scheduler] -.runs.-> ETL
    J -.runs.-> R
    J -.ping start/success/fail.-> HC[External health check]
```

Details: [ARCHITECTURE.md](ARCHITECTURE.md) · decisions: [docs/adr/](docs/adr/README.md) · current behaviour (pt-BR): [docs/como-funciona.md](docs/como-funciona.md).

## Quick start with the fictional data

Requirements: Python 3.12+ and any Postgres 13+ (local Supabase, or a plain container as below).

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# A throwaway Postgres for the demo
docker run -d --name treino-demo -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:17
export DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/postgres

python init_db.py                         # apply supabase/migrations/*.sql
mkdir -p data/raw && cp examples/hevy/* data/raw/
python import_hevy.py                     # fictional Hevy backup -> Postgres
python apply_aliases.py                   # reviewed canonical exercise names
python import_obsidian.py                 # fictional Obsidian logs (examples/obsidian)
python import_hevy.py                     # run again: counts do not change
python verify.py                          # views vs. independent recount
python report.py --all                    # reports/relatorio-YYYY-MM-DD.md
python load_steps.py                      # reports/cargas-*.md
```

With a local Supabase instead (`npx --yes supabase start`), migrations are applied automatically and the default `DATABASE_URL` (port 58322) already points to it.

With real accounts: copy `.env.example` to `.env`, fill `HEVY_API_KEY` (and `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET`), then `python check.py`, `python dump.py`, `python sync.py`, `python strava_auth.py` once and `python sync_strava.py`. Scheduled runs: `python job.py sync` and `python job.py relatorio`, with `HEALTHCHECK_URL_SYNC` / `HEALTHCHECK_URL_RELATORIO` set.

## Tests

```bash
python -m unittest discover -p "test_*.py" -v
```

The tests need no network and no database. CI runs them plus a [gitleaks](https://github.com/gitleaks/gitleaks) secret scan on every push.

## Notes

- Code comments, reports and the coach prompt are in Brazilian Portuguese; the top-level docs are in English.
- Next steps: [docs/next-steps.md](docs/next-steps.md).

## License

MIT, see [LICENSE](LICENSE).
