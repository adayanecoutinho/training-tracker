"""Start of comparable training history (e.g. when the current gym started).

Set TRAINING_HISTORY_START=YYYY-MM-DD in the environment or .env; the default is
a fictional date used by the demo data.
"""
import os
from datetime import date, timedelta

from env import load_env

DEFAULT_HISTORY_START = "2026-01-05"


def history_start():
    load_env()
    return date.fromisoformat(os.environ.get("TRAINING_HISTORY_START") or DEFAULT_HISTORY_START)


VALID_HISTORY_START = history_start()


def period_start(today, *, weeks=None, since=None):
    if since is not None:
        return date.fromisoformat(since) if isinstance(since, str) else since
    if weeks is None:
        return VALID_HISTORY_START
    if weeks < 1:
        raise ValueError('--weeks deve ser pelo menos 1')
    monday = today - timedelta(days=today.weekday())
    return max(VALID_HISTORY_START, monday - timedelta(weeks=weeks - 1))
