CREATE TABLE cardio_sessions (
    strava_id bigint PRIMARY KEY,
    start_time timestamptz NOT NULL,
    local_date date NOT NULL,
    name text,
    sport_type text NOT NULL,
    distance_m numeric,
    moving_time_s int,
    elapsed_time_s int,
    elevation_gain_m numeric,
    avg_speed_mps numeric,
    max_speed_mps numeric,
    avg_heartrate numeric,
    max_heartrate numeric,
    relative_effort numeric,
    calories numeric,
    is_commute boolean,
    is_trainer boolean,
    synced_at timestamptz DEFAULT now()
);

CREATE VIEW v_weekly_cardio AS
SELECT date_trunc('week', local_date)::date AS week_start,
       count(*) AS sessions,
       count(*) FILTER (WHERE moving_time_s >= 1200) AS sessions_20min,
       sum(moving_time_s) / 60.0 AS minutes,
       sum(distance_m) / 1000.0 AS km
FROM cardio_sessions
GROUP BY 1;
