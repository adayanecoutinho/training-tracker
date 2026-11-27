"""Degraus de carga observados; não define progressões nem recomendações."""
from collections import defaultdict
from datetime import date

from db import connect
from report import OUT, fmt, table
from history_config import VALID_HISTORY_START

SINCE = VALID_HISTORY_START
SCALE_WARNING = 'possível troca de máquina/escala'


def scale_changes(rows):
    """Compara máximos positivos de sessões consecutivas, em todo o histórico."""
    sessions = defaultdict(dict)
    for name, session_id, stamp, day, weight, count in rows:
        if weight > 0:
            key = (stamp, str(session_id), day)
            sessions[name][key] = max(sessions[name].get(key, weight), weight)
    changes = defaultdict(list)
    for name, history in sessions.items():
        previous = None
        for key, weight in sorted(history.items()):
            if previous:
                prior_day, prior_weight = previous
                if max(prior_weight, weight) > 2 * min(prior_weight, weight):
                    changes[name].append((prior_day, prior_weight, key[2], weight))
            previous = (key[2], weight)
    return changes


def render_load_steps(rows, changes, since=None):
    grouped = defaultdict(lambda: defaultdict(list))
    latest = {}
    for name, session_id, stamp, day, weight, count in rows:
        if since and day < since:
            continue
        grouped[name][weight].append((day, count))
        key = (stamp, str(session_id))
        if name not in latest or key > latest[name][0]:
            latest[name] = (key, day, {weight})
        elif key == latest[name][0]:
            latest[name][2].add(weight)
    lines = ['# Cargas por exercício', '',
             'degraus inferidos do histórico, a confirmar por foto das máquinas', '',
             f'Período: desde {since.isoformat()} (inclusive).' if since else 'Período: histórico completo.', '',
             'Contagens representam séries não-aquecimento de sessões não excluídas. '
             'Cargas nulas são omitidas; zero é mantido quando registrado. '
             'Datas no fuso America/Sao_Paulo. Uso único é sinalizado para conferência, '
             'sem corrigir registros.', '',
             'A carga do último uso lista todos os pesos registrados na sessão mais recente. '
             'A sinalização de escala compara a maior carga positiva entre sessões consecutivas; '
             'razões maiores que 2× são indicadas nos dois sentidos. '
             'Na geração dos arquivos, a comparação usa somente as sessões do período selecionado. '
             'A sinalização é uma hipótese para conferência, não uma correção.', '',
             '## Resumo', '']
    visible_changes = {name: [r for r in changes.get(name, []) if not since or r[2] >= since]
                       for name in grouped}
    table(lines, ['Exercício', 'Carga do último uso (kg)', 'Data do último uso',
                  f'Degraus distintos desde {since}' if since else 'Degraus distintos (histórico completo)',
                  'Observação'],
          [(name, ' / '.join(map(str, sorted(latest[name][2]))), latest[name][1],
            ', '.join(map(str, sorted(grouped[name]))),
            SCALE_WARNING if visible_changes[name] else '—') for name in sorted(grouped)])
    for name in sorted(grouped):
        loads = grouped[name]
        lines += [f'## {name}', '',
                  f'Mínimo: {fmt(min(loads))} kg; máximo: {fmt(max(loads))} kg; '
                  f'último uso do exercício: {latest[name][1]}.', '']
        if visible_changes[name]:
            lines += [f'Observação: {SCALE_WARNING}.', '']
            table(lines, ['Sessão anterior', 'Maior carga anterior (kg)',
                          'Sessão seguinte', 'Maior carga seguinte (kg)'], visible_changes[name])
        table(lines, ['Carga (kg)', 'Usos (séries)', 'Primeiro uso', 'Último uso', 'Sinalização'],
              [(weight, sum(n for _, n in uses), min(d for d, _ in uses), max(d for d, _ in uses),
                'Uso único: possível erro de digitação; conferir' if sum(n for _, n in uses) == 1 else '—')
               for weight, uses in sorted(loads.items())])
    if not grouped:
        lines += ['Nenhuma carga registrada.', '']
    return '\n'.join(lines), len(grouped)


def make_load_steps(since=VALID_HISTORY_START, all_history=False):
    with connect() as conn:
        rows = conn.execute(
            "SELECT e.canonical_name,w.id,w.start_time,"
            "(w.start_time AT TIME ZONE 'America/Sao_Paulo')::date,s.weight_kg,COUNT(*) "
            "FROM sets s JOIN exercises e ON e.id=s.exercise_id "
            "JOIN workouts w ON w.id=s.workout_id "
            "WHERE s.set_type<>'warmup' AND w.deleted_at IS NULL AND s.weight_kg IS NOT NULL "
            "GROUP BY e.canonical_name,w.id,w.start_time,s.weight_kg "
            "ORDER BY e.canonical_name,w.start_time,w.id,s.weight_kg"
        ).fetchall()
    OUT.mkdir(exist_ok=True)
    outputs = [('cargas-historico-completo.md', None)] if all_history else [
        ('cargas-por-exercicio.md', since), ('cargas-historico-completo.md', None)]
    for filename, cutoff in outputs:
        eligible = [r for r in rows if cutoff is None or r[3] >= cutoff]
        text, count = render_load_steps(eligible, scale_changes(eligible), cutoff)
        path = OUT / filename
        path.write_text(text, encoding='utf-8')
        print(f'Relatório gerado: {path} ({count} exercícios)')
    return OUT / ('cargas-historico-completo.md' if all_history else 'cargas-por-exercicio.md')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    period = parser.add_mutually_exclusive_group()
    period.add_argument('--since', type=date.fromisoformat, default=VALID_HISTORY_START)
    period.add_argument('--all', action='store_true', dest='all_history')
    args = parser.parse_args()
    make_load_steps(since=args.since, all_history=args.all_history)
