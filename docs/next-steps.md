---
description: Next technical steps for the public repository.
---

# Next steps

1. **Unify the scripts into one CLI.** One entry point, e.g. `treino dump | import-hevy | sync-hevy | import-obsidian | sync-strava | aliases generate|apply | verify | report | load-steps | job`, sharing argument parsing, logging and exit codes. `strava_auth.py` becomes a `setup strava` subcommand.
2. **Evaluate the coach with synthetic weeks.** Build a small set of fictional weeks (progressing, stalled, missed sessions, RPE above target, conflicting sources) with the expected review for each, and check that the coach cites its sources, keeps the current rules, stays within training topics and writes only to the inbox.
3. **Move the code into `src/`.** A `src/treino_evolucao/` package with a `pyproject.toml`, tests under `tests/`, and the current scripts kept as thin wrappers during the transition.
4. **Database tests in CI.** Run the fictional quick start (migrations, imports twice, `verify.py`) against a Postgres service container.
