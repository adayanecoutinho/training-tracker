-- Permite reunir vários IDs do Hevy sob um exercício canônico sem perder
-- a associação usada pelas importações incrementais seguintes.
CREATE TABLE public.exercise_hevy_templates (
    template_id text PRIMARY KEY,
    exercise_id uuid NOT NULL REFERENCES public.exercises(id) ON DELETE CASCADE
);
CREATE INDEX exercise_hevy_templates_exercise_idx
    ON public.exercise_hevy_templates(exercise_id);
