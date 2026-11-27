# 0005. Scheduled job monitored by an external health check

## Context

The sync and the weekly report run unattended. A silent failure (expired token, database down, scheduler not firing) would leave the coach reviewing stale data.

## Decision

`job.py` wraps each job (`sync`, `relatorio`): it pings `<url>/start`, runs the steps in order, and pings `<url>` on success or `<url>/fail` on the first failing step. The ping URL comes from an environment variable and is never printed; the failure ping carries only the step name and exit code, not the output. A failed ping does not fail the job. The container image only keeps a process alive; the scheduler runs `python job.py <name>` inside it.

## Alternatives considered

- **Log-only monitoring.** Nobody reads the logs of a job that did not run.
- **Email sent by the script itself.** Cannot report that the job never started.
- **Container health check that tests the database.** Would mark the container unhealthy for an unrelated outage; the image health check only verifies that Python and its dependencies load.

## Consequences

- Missed runs and failures are visible from outside (dead man's switch).
- Secrets in the ping URL cannot leak through logs or alert bodies; `test_job.py` asserts this.
- Each job needs its own check URL (`HEALTHCHECK_URL_SYNC`, `HEALTHCHECK_URL_RELATORIO`).
