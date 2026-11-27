"""Cardio incremental, sem persistir mapas, coordenadas ou JSON bruto."""
import time
from datetime import datetime

from db import connect
from strava_client import Client

FIELDS = ('strava_id', 'start_time', 'local_date', 'name', 'sport_type', 'distance_m',
          'moving_time_s', 'elapsed_time_s', 'elevation_gain_m', 'avg_speed_mps',
          'max_speed_mps', 'avg_heartrate', 'max_heartrate', 'relative_effort',
          'calories', 'is_commute', 'is_trainer')
SOURCE = ('id', 'start_date', 'start_date_local', 'name', 'sport_type', 'distance',
          'moving_time', 'elapsed_time', 'total_elevation_gain', 'average_speed',
          'max_speed', 'average_heartrate', 'max_heartrate', 'suffer_score',
          'calories', 'commute', 'trainer')


def is_hevy(activity):
    return (activity.get('sport_type', activity.get('type')) == 'WeightTraining' or
            (activity.get('description') or '').startswith('Registrado com hevyapp.com'))


def main():
    client = Client()
    imported = updated = ignored = 0
    with connect() as conn:
        row = conn.execute("SELECT value FROM sync_state WHERE key='strava_last_start'").fetchone()
        cursor = row[0] if row else None
    # Um segundo de sobreposição evita perder atividades com timestamp igual.
    after = int(datetime.fromisoformat(cursor.replace('Z', '+00:00')).timestamp()) - 1 if cursor else None
    latest = cursor
    page = 1
    while True:
        params = dict(per_page=100, page=page)
        if after is not None:
            params['after'] = after
        activities = client.get('/athlete/activities', **params)
        if not activities:
            break
        for activity in activities:
            stamp = activity['start_date']
            if latest is None or stamp > latest:
                latest = stamp
            if is_hevy(activity):
                ignored += 1
                continue
            with connect() as conn:
                exists = conn.execute('SELECT 1 FROM cardio_sessions WHERE strava_id=%s',
                                      (activity['id'],)).fetchone() is not None
            if not exists:
                time.sleep(1)
                activity = client.get(f"/activities/{activity['id']}")
                if is_hevy(activity):
                    ignored += 1
                    continue
            values = [activity.get(k) for k in SOURCE]
            values[2] = activity['start_date_local'][:10]
            values[4] = activity.get('sport_type') or activity['type']
            changes = ','.join(f'{f}=EXCLUDED.{f}' for f in FIELDS[1:] if f != 'calories')
            changes += ',calories=COALESCE(EXCLUDED.calories,cardio_sessions.calories),synced_at=now()'
            with connect() as conn:
                conn.execute(f"INSERT INTO cardio_sessions ({','.join(FIELDS)}) VALUES "
                             f"({','.join(['%s'] * len(FIELDS))}) ON CONFLICT (strava_id) "
                             f"DO UPDATE SET {changes}", values)
            imported += not exists
            updated += exists
        page += 1
    # Só avançar o cursor após concluir todas as páginas; falhas são retomáveis por upsert.
    with connect() as conn:
        if latest:
            conn.execute("INSERT INTO sync_state(key,value) VALUES ('strava_last_start',%s) "
                         "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", (latest,))
        total = conn.execute('SELECT count(*) FROM cardio_sessions').fetchone()[0]
    print(f'Importadas: {imported}; atualizadas: {updated}; ignoradas por serem cópias do Hevy: {ignored}; total no banco: {total}')


if __name__ == '__main__':
    main()
