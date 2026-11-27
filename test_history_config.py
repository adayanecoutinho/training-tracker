"""Recorte padrão do histórico comparável e sobrescrita explícita."""
import os
import unittest
from datetime import date
from unittest.mock import patch

import history_config
from history_config import DEFAULT_HISTORY_START, VALID_HISTORY_START, period_start


class HistoryConfigTests(unittest.TestCase):
    def test_default_boundary_and_explicit_override(self):
        if os.environ.get("TRAINING_HISTORY_START"):
            self.skipTest("TRAINING_HISTORY_START definido no ambiente")
        today = date(2026, 6, 24)
        self.assertEqual(VALID_HISTORY_START, date.fromisoformat(DEFAULT_HISTORY_START))
        self.assertEqual(period_start(today), VALID_HISTORY_START)
        self.assertEqual(period_start(today, weeks=100), VALID_HISTORY_START)
        self.assertEqual(period_start(today, weeks=1), date(2026, 6, 22))
        self.assertEqual(period_start(today, since='2025-01-01'), date(2025, 1, 1))

    def test_weeks_must_be_positive(self):
        with self.assertRaises(ValueError):
            period_start(date(2026, 6, 24), weeks=0)

    def test_environment_variable_overrides_default(self):
        with patch.dict(os.environ, {"TRAINING_HISTORY_START": "2026-02-02"}):
            self.assertEqual(history_config.history_start(), date(2026, 2, 2))


if __name__ == '__main__':
    unittest.main()
