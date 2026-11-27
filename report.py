"""Relatório descritivo para avaliação externa, sem recomendações."""

import argparse
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from db import connect
from history_config import VALID_HISTORY_START, period_start

OUT = Path(__file__).resolve().parent / "reports"


def fmt(value, suffix=""):
    return "—" if value is None else f"{value}{suffix}"


def cardio_fmt(value):
    return "—" if value is None else str(Decimal(str(value)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP))


def table(lines, columns, rows):
    lines.extend(["| " + " | ".join(columns) + " |",
                  "| " + " | ".join("---" for _ in columns) + " |"])
    for row in rows:
        lines.append("| " + " | ".join(str(col).replace("|", "\\|").replace("\n", " ")
                                       for col in row) + " |")
    if not rows:
        lines.append("| " + " | ".join("—" for _ in columns) + " |")
    lines.append("")


def make_report(weeks=None, today=None, since=None, all_history=False):
    if sum((weeks is not None, since is not None, all_history)) > 1:
        raise ValueError("--weeks, --since e --all não podem ser usados juntos")
    if weeks is not None and weeks < 1:
        raise ValueError("--weeks deve ser pelo menos 1")
    today = today or date.today()
    current_monday = today - timedelta(days=today.weekday())
    if isinstance(since, str):
        since = date.fromisoformat(since)
    if since and since > today:
        raise ValueError("--since não pode ser uma data futura")
    if all_history:
        with connect() as conn:
            row = conn.execute("SELECT MIN(day) FROM (SELECT date AS day FROM v_session_summary "
                               "UNION ALL SELECT local_date FROM cardio_sessions) dates").fetchone()
        start = row[0] or today
    else:
        start = period_start(today, weeks=weeks, since=since)
    first_monday = start - timedelta(days=start.weekday())
    week_starts = [first_monday + timedelta(weeks=i)
                   for i in range((current_monday - first_monday).days // 7 + 1)]
    end = today + timedelta(days=1)
    period_label = ("histórico completo" if all_history else
                    f"desde {start.isoformat()}" if weeks is None else
                    f"{weeks} semanas ISO, incluindo a atual")
    lines = [f"# Relatório de treinos — {today.isoformat()}", "",
             f"Período: {start.isoformat()} a {today.isoformat()} ({period_label}).", "",
             "## Sessões", ""]
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT date,source,title,duration_minutes,effective_sets,avg_rpe "
                "FROM v_session_summary WHERE date >= %s AND date < %s ORDER BY date, title",
                (start, end),
            )
            sessions = cur.fetchall()
            table(lines, ["Data", "Origem", "Treino", "Duração (min)", "Séries efetivas", "RPE médio"],
                  [(day, source, title or "—", fmt(duration), count, fmt(rpe))
                   for day, source, title, duration, count, rpe in sessions])

            lines += ["## Cardio", ""]
            # Usar a view nas semanas completas e reagrupar apenas nas bordas do período.
            cur.execute(
                "SELECT week_start,sessions,sessions_20min,minutes,km FROM v_weekly_cardio "
                "WHERE week_start >= %s AND week_start + 6 < %s "
                "UNION ALL SELECT date_trunc('week',local_date)::date,COUNT(*),"
                "COUNT(*) FILTER (WHERE moving_time_s>=1200),SUM(moving_time_s)/60.0,"
                "SUM(distance_m)/1000.0 FROM cardio_sessions "
                "WHERE local_date >= %s AND local_date < %s "
                "AND NOT (date_trunc('week',local_date)::date >= %s "
                "AND date_trunc('week',local_date)::date + 6 < %s) "
                "GROUP BY 1 ORDER BY 1", (start, end, start, end, start, end))
            table(lines, ["Semana ISO", "Sessões", "Sessões ≥ 20 min", "Minutos", "km"],
                  [(f"{day.isocalendar().year}-{day.isocalendar().week:02d}", count,
                    long_count, cardio_fmt(minutes), cardio_fmt(km))
                   for day, count, long_count, minutes, km in cur.fetchall()])
            cur.execute(
                "SELECT local_date,name,sport_type,distance_m/1000,moving_time_s/60.0 "
                "FROM cardio_sessions WHERE local_date >= %s AND local_date < %s "
                "ORDER BY local_date,start_time,strava_id", (start, end))
            table(lines, ["Data", "Atividade", "Tipo", "km", "Minutos em movimento"],
                  [(day, name or '—', sport, cardio_fmt(km), cardio_fmt(minutes))
                   for day, name, sport, km, minutes in cur.fetchall()])

            # Exibir as datas esclarece semanas com igual volume e treinos distintos.
            days_by_week = defaultdict(list)
            for day, *_ in sessions:
                monday = day - timedelta(days=day.weekday())
                days_by_week[monday].append(day.strftime("%d/%m"))

            lines += ["## Volume semanal por músculo (séries ponderadas)", "",
                      "Músculo primário = 1 série; secundário = 0,5 série. "
                      "Aquecimentos excluídos. As datas incluem sessões só de cardio, "
                      "que não somam volume muscular quando não possuem músculo associado.", ""]
            cur.execute(
                "WITH eligible AS ("
                " SELECT date_trunc('week', w.start_time AT TIME ZONE 'America/Sao_Paulo')::date "
                " AS week_start, e.primary_muscle, e.secondary_muscles "
                " FROM sets s JOIN workouts w ON w.id=s.workout_id "
                " JOIN exercises e ON e.id=s.exercise_id "
                " WHERE w.deleted_at IS NULL AND s.set_type<>'warmup' "
                " AND (w.start_time AT TIME ZONE 'America/Sao_Paulo')::date BETWEEN %s AND %s"
                "), muscles AS ("
                " SELECT week_start,primary_muscle AS muscle,1.0::numeric AS contribution "
                " FROM eligible WHERE primary_muscle IS NOT NULL AND primary_muscle<>'' "
                " UNION ALL "
                " SELECT week_start, secondary.muscle,0.5::numeric "
                " FROM eligible CROSS JOIN LATERAL ("
                " SELECT DISTINCT muscle FROM unnest(secondary_muscles) AS m(muscle) "
                " WHERE muscle<>'' AND muscle IS DISTINCT FROM primary_muscle"
                " ) secondary"
                ") SELECT week_start,muscle,SUM(contribution) FROM muscles "
                " GROUP BY week_start,muscle ORDER BY week_start,muscle",
                (start, today),
            )
            volume = defaultdict(dict)
            muscles = set()
            for monday, muscle, effective in cur.fetchall():
                volume[monday][muscle] = effective
                muscles.add(muscle)
            muscles = sorted(muscles)
            table(lines, ["Semana ISO", "Sessões (datas)"] + muscles,
                  [[f"{monday.isocalendar().year}-{monday.isocalendar().week:02d}",
                    ", ".join(days_by_week[monday]) or "—"] +
                   [fmt(volume[monday].get(muscle, 0)) for muscle in muscles]
                   for monday in week_starts])

            lines += ["## Progressão dos 10 exercícios mais frequentes", ""]
            cur.execute(
                "SELECT e.id,e.canonical_name,COUNT(DISTINCT w.id) AS frequency "
                "FROM sets s JOIN workouts w ON w.id=s.workout_id "
                "JOIN exercises e ON e.id=s.exercise_id "
                "WHERE w.deleted_at IS NULL AND (w.start_time AT TIME ZONE 'America/Sao_Paulo')::date "
                "BETWEEN %s AND %s AND s.set_type<>'warmup' "
                "GROUP BY e.id,e.canonical_name ORDER BY frequency DESC,e.canonical_name LIMIT 10",
                (start, today),
            )
            frequent = cur.fetchall()
            for exercise_id, canonical, frequency in frequent:
                lines += [f"### {canonical} ({frequency} sessões)", ""]
                cur.execute(
                    "SELECT date,best_weight_kg,best_reps,best_e1rm,max_weight_kg,reps_at_max_weight "
                    "FROM v_exercise_progression WHERE exercise_id=%s AND date BETWEEN %s AND %s "
                    "ORDER BY date", (exercise_id, start, today),
                )
                table(lines, ["Data", "Melhor série (kg × reps)", "e1RM (kg)", "Carga máx. (kg × reps)"],
                      [(day, f"{fmt(weight)} × {fmt(reps)}", fmt(e1rm),
                        f"{fmt(max_weight)} × {fmt(max_reps)}")
                       for day, weight, reps, e1rm, max_weight, max_reps in cur.fetchall()])
            if not frequent:
                lines += ["Nenhum exercício no período.", ""]

            lines += ["## Séries em falha ou RPE ≥ 9,5", ""]
            cur.execute(
                "SELECT (w.start_time AT TIME ZONE 'America/Sao_Paulo')::date, w.title, "
                "e.canonical_name,s.exercise_order,s.set_index,s.set_type,s.weight_kg,s.reps,s.rpe "
                "FROM sets s JOIN workouts w ON w.id=s.workout_id "
                "JOIN exercises e ON e.id=s.exercise_id "
                "WHERE w.deleted_at IS NULL AND (w.start_time AT TIME ZONE 'America/Sao_Paulo')::date "
                "BETWEEN %s AND %s AND (s.set_type='failure' OR s.rpe>=9.5) "
                "ORDER BY w.start_time,s.exercise_order,s.set_index", (start, today),
            )
            table(lines, ["Data", "Treino", "Exercício", "Posição", "Tipo", "Carga", "Reps", "RPE"],
                  [(day, title or "—", name, f"{order+1}.{index+1}", set_type,
                    fmt(weight), fmt(reps), fmt(rpe))
                   for day, title, name, order, index, set_type, weight, reps, rpe in cur.fetchall()])

            lines += ["## Variações suspeitas de carga (> 50%)", "",
                      "Comparação da maior carga positiva por exercício entre sessões consecutivas; "
                      "a sessão anterior pode estar fora do período do relatório. "
                      "Variação superior a 50% é sinalizada como possível troca de máquina/escala ou erro de registro. "
                      "Marcações para conferência dos registros, sem alterar cargas.", ""]
            cur.execute(
                "WITH per_session AS ("
                " SELECT w.id AS workout_id,w.start_time,"
                " (w.start_time AT TIME ZONE 'America/Sao_Paulo')::date AS day,"
                " e.id AS exercise_id,e.canonical_name,MAX(s.weight_kg) AS max_kg"
                " FROM sets s JOIN workouts w ON w.id=s.workout_id"
                " JOIN exercises e ON e.id=s.exercise_id"
                " WHERE w.deleted_at IS NULL AND s.set_type<>'warmup' AND s.weight_kg>0"
                " AND (w.start_time AT TIME ZONE 'America/Sao_Paulo')::date >= %s"
                " GROUP BY w.id,w.start_time,e.id,e.canonical_name"
                "), compared AS ("
                " SELECT *,"
                " LAG(day) OVER(PARTITION BY exercise_id ORDER BY start_time,workout_id) AS prev_day,"
                " LAG(max_kg) OVER(PARTITION BY exercise_id ORDER BY start_time,workout_id) AS prev_kg"
                " FROM per_session"
                ") SELECT day,canonical_name,prev_day,prev_kg,max_kg,"
                " ROUND(100*(max_kg-prev_kg)/prev_kg,1) AS change_pct"
                " FROM compared WHERE day BETWEEN %s AND %s AND prev_kg IS NOT NULL"
                " AND ABS(max_kg-prev_kg)>prev_kg*0.5"
                " ORDER BY day,canonical_name",
                (date.min if all_history or start < VALID_HISTORY_START else VALID_HISTORY_START, start, today),
            )
            table(lines, ["Data", "Exercício", "Sessão anterior", "Carga anterior (kg)",
                          "Carga atual (kg)", "Variação", "Sinalização"],
                  [(day, name, prior_day, fmt(prior), fmt(current),
                    f"{change:+}%", "possível troca de máquina/escala"
                    if max(prior, current) > 2 * min(prior, current)
                    else "Suspeito: conferir ambas")
                   for day, name, prior_day, prior, current, change in cur.fetchall()])

    lines += ["## Lacunas: semanas sem treino", ""]
    trained = {day - timedelta(days=day.weekday()) for day, *_ in sessions}
    gaps = [monday for monday in week_starts if monday not in trained]
    lines.extend([f"- {day.isocalendar().year}-{day.isocalendar().week:02d} ({day.isoformat()})"
                  for day in gaps] or ["Nenhuma."])
    lines.append("")
    OUT.mkdir(exist_ok=True)
    result = OUT / f"relatorio-{today.isoformat()}.md"
    result.write_text("\n".join(lines), encoding="utf-8")
    print(f"Relatório gerado: {result} ({len(sessions)} sessões, {len(gaps)} semanas sem treino)")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    period = parser.add_mutually_exclusive_group()
    period.add_argument("--weeks", type=int)
    period.add_argument("--since", type=date.fromisoformat, metavar="YYYY-MM-DD")
    period.add_argument("--all", action="store_true", dest="all_history")
    args = parser.parse_args()
    make_report(weeks=args.weeks, since=args.since, all_history=args.all_history)
