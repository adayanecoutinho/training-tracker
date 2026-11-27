"""Confere recorte temporal, cargas da última sessão e transições de escala."""
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal

from load_steps import SINCE, SCALE_WARNING, render_load_steps, scale_changes
from report import cardio_fmt


def row(name, day, weight, count=1):
    day = date.fromisoformat(day)
    stamp = datetime.combine(day, datetime.min.time(), timezone.utc)
    return name, day.isoformat(), stamp, day, Decimal(str(weight)), count


class LoadStepsTests(unittest.TestCase):
    def test_cutoff_summary_and_old_transition(self):
        # Valores fictícios; o corte é o padrão de history_config (2026-01-05).
        rows = [row('Extensora', '2025-12-10', 60),
                row('Extensora', '2026-01-20', 15, 3),
                row('Extensora', '2026-04-06', 20), row('Extensora', '2026-04-06', 25),
                row('Antigo', '2026-01-04', 10), row('Limite', '2026-01-05', 20)]
        changes = scale_changes(rows)
        recent, count = render_load_steps(rows, changes, SINCE)
        full, total = render_load_steps(rows, changes)
        self.assertEqual((count, total), (2, 3))
        self.assertNotIn('## Antigo', recent)
        self.assertIn('## Limite', recent)
        self.assertIn('| Extensora | 20 / 25 | 2026-04-06 | 15, 20, 25 |', recent)
        self.assertIn('| 2025-12-10 | 60 | 2026-01-20 | 15 |', recent)
        self.assertIn(SCALE_WARNING, recent)
        self.assertIn('15, 20, 25, 60', full)

    def test_strict_factor_two_and_zero(self):
        rows = [row('Teste', '2026-03-01', 0), row('Teste', '2026-03-02', 10),
                row('Teste', '2026-03-03', 20), row('Teste', '2026-03-04', 41),
                row('Teste', '2026-03-05', 20)]
        self.assertEqual(len(scale_changes(rows)['Teste']), 2)

    def test_cardio_one_decimal(self):
        self.assertEqual(cardio_fmt(Decimal('32.45000000')), '32.5')
        self.assertEqual(cardio_fmt(Decimal('4.5237')), '4.5')
        self.assertEqual(cardio_fmt(Decimal('10')), '10.0')
        self.assertEqual(cardio_fmt(None), '—')


if __name__ == '__main__':
    unittest.main()
