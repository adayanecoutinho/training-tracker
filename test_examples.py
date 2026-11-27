"""Confere, sem rede e sem banco, que os dados fictícios de examples/ seguem os formatos lidos pelo ETL."""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import obsidian_parser
from history_config import DEFAULT_HISTORY_START
from import_hevy import SET_TYPES

EXAMPLES = Path(__file__).resolve().parent / "examples"


def load(name):
    return json.loads((EXAMPLES / "hevy" / f"{name}.json").read_text(encoding="utf-8"))


class HevyExampleTests(unittest.TestCase):
    def test_backup_has_the_files_import_hevy_reads(self):
        for name in ("exercise_templates", "workouts", "body_measurements"):
            self.assertIsInstance(load(name), list)
        self.assertTrue((EXAMPLES / "hevy" / "_dumped_at.txt").exists())

    def test_workouts_reference_known_templates_and_valid_set_types(self):
        templates = {t["id"] for t in load("exercise_templates")}
        workouts = load("workouts")
        self.assertTrue(workouts)
        for workout in workouts:
            for key in ("id", "title", "start_time", "end_time", "updated_at", "exercises"):
                self.assertIn(key, workout)
            self.assertGreaterEqual(workout["start_time"][:10], DEFAULT_HISTORY_START)
            for exercise in workout["exercises"]:
                self.assertIn(exercise["exercise_template_id"], templates)
                for item in exercise["sets"]:
                    self.assertIn(item["type"], SET_TYPES)


class ObsidianExampleTests(unittest.TestCase):
    def test_parser_reads_the_demo_logs(self):
        with patch.dict(os.environ, {"OBSIDIAN_LOGS_DIR": str(EXAMPLES / "obsidian")}):
            sessions = obsidian_parser.logs()
        self.assertEqual(len(sessions), 4)
        titles = {title for _, title in sessions}
        self.assertIn("Descanso", titles)
        rows = [row for rows in sessions.values() for row in rows]
        sets = [s for row in rows for s in obsidian_parser.parsed_sets(row)]
        self.assertTrue(any(s["rir"] is not None for s in sets))
        # '16 (2×8)' vira 8 kg por haltere, com o texto original na nota.
        self.assertTrue(any(s["weight_kg"] == 8.0 and "Peso original" in (s["notes"] or "") for s in sets))
        self.assertTrue(any(row["cardio_seconds"] == 1200 for row in rows))


if __name__ == "__main__":
    unittest.main()
