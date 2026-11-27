# 0003. Canonical exercise names through a human-reviewed alias file

## Context

The same movement appears under different names: English and Portuguese Hevy titles, custom templates, free text in the logs. Volume and progression per exercise are meaningless if one exercise is split across several names, and wrong if two different exercises are merged.

## Decision

- `generate_aliases.py` writes `exercise_aliases.csv` (source, name, canonical name) from the names actually present in the data. `canonical_aliases.py` holds the obvious equivalences and takes priority.
- A person reviews the CSV. Uncertain names stay without a canonical name instead of being guessed.
- `apply_aliases.py` applies the CSV and merges exercises with the same canonical name, re-pointing their sets and template links (`exercise_hevy_templates`).

## Alternatives considered

- **Fuzzy matching at import time.** Fast, but silently merges different movements (machine vs. dumbbell, bilateral vs. single-leg).
- **An LLM picking matches.** Same risk, and not reproducible.
- **Keep raw names.** Splits the history of each exercise.

## Consequences

- Merges are explicit, versioned and reversible by editing the CSV.
- New exercises show up as unmapped until reviewed, which is visible in the output of `apply_aliases.py`.
