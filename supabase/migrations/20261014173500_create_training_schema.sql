-- Estrutura de armazenamento para dados brutos de treinos e acompanhamento.
-- TODO(metodologia): is_unilateral e spine_load serão definidos pelo Claude.

CREATE TABLE public.exercises (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    hevy_template_id text UNIQUE,
    name text NOT NULL,
    canonical_name text NOT NULL,
    primary_muscle text,
    secondary_muscles text[] NOT NULL DEFAULT '{}',
    equipment text,
    is_unilateral boolean,
    spine_load text CHECK (spine_load IN ('baixa', 'media', 'alta'))
);

CREATE TABLE public.workouts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source text NOT NULL CHECK (source IN ('hevy', 'obsidian')),
    hevy_id text UNIQUE,
    title text,
    description text,
    routine_id text,
    start_time timestamptz NOT NULL,
    end_time timestamptz,
    updated_at timestamptz,
    deleted_at timestamptz
);

CREATE TABLE public.sets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workout_id uuid NOT NULL REFERENCES public.workouts(id) ON DELETE CASCADE,
    exercise_id uuid NOT NULL REFERENCES public.exercises(id),
    exercise_order integer NOT NULL,
    set_index integer NOT NULL,
    set_type text NOT NULL CHECK (set_type IN ('warmup', 'normal', 'failure', 'dropset')),
    weight_kg numeric,
    reps integer,
    duration_seconds integer,
    distance_meters integer,
    rpe numeric,
    rir numeric,
    notes text,
    UNIQUE (workout_id, exercise_order, set_index)
);

CREATE TABLE public.body_metrics (
    date date PRIMARY KEY,
    weight_kg numeric,
    body_fat_pct numeric,
    lean_mass_kg numeric,
    measurements jsonb NOT NULL DEFAULT '{}'::jsonb,
    source text NOT NULL
);

CREATE TABLE public.daily_checkins (
    date date PRIMARY KEY,
    sleep_hours numeric,
    sleep_quality integer CHECK (sleep_quality BETWEEN 1 AND 5),
    energy integer CHECK (energy BETWEEN 1 AND 5),
    notes text
);

CREATE TABLE public.mesocycles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    structure text,
    start_date date NOT NULL,
    end_date date,
    notes text
);

CREATE TABLE public.mesocycle_weeks (
    mesocycle_id uuid NOT NULL REFERENCES public.mesocycles(id) ON DELETE CASCADE,
    week_number integer NOT NULL,
    phase text,
    rpe_target_min numeric,
    rpe_target_max numeric,
    PRIMARY KEY (mesocycle_id, week_number)
);

CREATE TABLE public.sync_state (
    key text PRIMARY KEY,
    value text
);

CREATE INDEX workouts_start_time_idx ON public.workouts(start_time);
CREATE INDEX sets_exercise_id_idx ON public.sets(exercise_id);

-- Séries efetivas = toda série que não seja aquecimento.
-- Treinos removidos no Hevy ficam armazenados, mas são excluídos das análises.
CREATE VIEW public.v_session_summary AS
SELECT
    w.id AS workout_id,
    w.source,
    (w.start_time AT TIME ZONE 'America/Sao_Paulo')::date AS date,
    w.title,
    ROUND(EXTRACT(EPOCH FROM (w.end_time - w.start_time)) / 60.0, 1) AS duration_minutes,
    COUNT(s.id) FILTER (WHERE s.set_type <> 'warmup') AS effective_sets,
    COALESCE(SUM(s.weight_kg * s.reps), 0) AS tonnage_kg,
    ROUND(AVG(s.rpe) FILTER (WHERE s.set_type <> 'warmup'), 2) AS avg_rpe
FROM public.workouts w
LEFT JOIN public.sets s ON s.workout_id = w.id
WHERE w.deleted_at IS NULL
GROUP BY w.id, w.source, w.start_time, w.end_time, w.title;

-- A semana começa na segunda-feira (ISO); músculo principal vale 1,
-- cada secundário distinto do principal vale 0,5 por série efetiva.
CREATE VIEW public.v_weekly_volume_by_muscle AS
WITH effective_sets AS (
    SELECT
        date_trunc('week', w.start_time AT TIME ZONE 'America/Sao_Paulo')::date AS week_start,
        e.primary_muscle,
        e.secondary_muscles
    FROM public.sets s
    JOIN public.workouts w ON w.id = s.workout_id
    JOIN public.exercises e ON e.id = s.exercise_id
    WHERE w.deleted_at IS NULL AND s.set_type <> 'warmup'
), weighted_muscles AS (
    SELECT week_start, primary_muscle AS muscle, 1.0::numeric AS contribution
    FROM effective_sets
    WHERE primary_muscle IS NOT NULL AND primary_muscle <> ''
    UNION ALL
    SELECT es.week_start, secondary.muscle, 0.5::numeric AS contribution
    FROM effective_sets es
    CROSS JOIN LATERAL (
        SELECT DISTINCT muscle
        FROM unnest(es.secondary_muscles) AS m(muscle)
        WHERE muscle <> '' AND muscle IS DISTINCT FROM es.primary_muscle
    ) secondary
)
SELECT
    week_start,
    to_char(week_start, 'IYYY-IW') AS iso_week,
    muscle,
    SUM(contribution) AS effective_sets
FROM weighted_muscles
GROUP BY week_start, muscle;

-- Uma linha por exercício em cada sessão; melhor série por e1RM de Epley,
-- e carga máxima com as repetições correspondentes.
CREATE VIEW public.v_exercise_progression AS
WITH eligible_sets AS (
    SELECT
        w.id AS workout_id,
        (w.start_time AT TIME ZONE 'America/Sao_Paulo')::date AS date,
        e.id AS exercise_id,
        e.canonical_name,
        s.exercise_order,
        s.set_index,
        s.weight_kg,
        s.reps,
        CASE WHEN s.weight_kg IS NOT NULL AND s.reps > 0
            THEN ROUND(s.weight_kg * (1 + s.reps / 30.0), 2)
        END AS e1rm
    FROM public.sets s
    JOIN public.workouts w ON w.id = s.workout_id
    JOIN public.exercises e ON e.id = s.exercise_id
    WHERE w.deleted_at IS NULL AND s.set_type <> 'warmup'
), ranked AS (
    SELECT *,
        row_number() OVER (
            PARTITION BY workout_id, exercise_id
            ORDER BY e1rm DESC NULLS LAST, weight_kg DESC NULLS LAST,
                     reps DESC NULLS LAST, exercise_order, set_index
        ) AS best_rank,
        row_number() OVER (
            PARTITION BY workout_id, exercise_id
            ORDER BY weight_kg DESC NULLS LAST, reps DESC NULLS LAST,
                     exercise_order, set_index
        ) AS max_weight_rank
    FROM eligible_sets
)
SELECT
    best.workout_id,
    best.date,
    best.exercise_id,
    best.canonical_name,
    best.weight_kg AS best_weight_kg,
    best.reps AS best_reps,
    best.e1rm AS best_e1rm,
    heaviest.weight_kg AS max_weight_kg,
    heaviest.reps AS reps_at_max_weight
FROM ranked best
JOIN ranked heaviest
    ON heaviest.workout_id = best.workout_id
    AND heaviest.exercise_id = best.exercise_id
    AND heaviest.max_weight_rank = 1
WHERE best.best_rank = 1;
