"""Leitura SOMENTE LEITURA dos logs markdown de treinos de 2026."""

import os
import re
import unicodedata
from collections import OrderedDict
from datetime import date
from pathlib import Path

from env import load_env

DEFAULT_LOGS_DIR = Path(__file__).resolve().parent / "examples" / "obsidian"


def logs_dir() -> Path:
    """Pasta com os logs de treino do Obsidian; OBSIDIAN_LOGS_DIR no .env sobrescreve."""
    load_env()
    return Path(os.environ.get("OBSIDIAN_LOGS_DIR") or DEFAULT_LOGS_DIR)


FILES = ("marco", "abril", "maio", "junho")
MISSING = {"", "—", "-", "–", "[ ]", "n/a", "null"}


def normalized(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value.lower())
                   if not unicodedata.combining(c)).strip()


def series(value):
    return [s.strip() for s in re.split(r"\s*/\s*", value.strip())] if value.strip() not in MISSING else []


def number(value):
    if not value or value.strip().lower() in MISSING:
        return None
    value = value.strip().replace(",", ".")
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value):
        return float(value)
    return None


def repeats(items, index):
    if not items:
        return ""
    return items[index] if index < len(items) else (items[0] if len(items) == 1 else "")


def parse_weight(value):
    # '16 (2×8)' é o total dos dois halteres: registrar carga por mão.
    match = re.search(r"\(\s*2\s*[×x]\s*(\d+(?:[.,]\d+)?)\s*\)", value)
    if match:
        return number(match.group(1)), value.strip()
    return number(value), None


def parse_cardio(value):
    if not value or value.strip().lower() in MISSING:
        return None, None
    m = re.search(r"(?i)\b(esteira|bike|bicicleta|remo|corda)\s*(\d+(?:[.,]\d+)?)", value)
    if m:
        return m.group(1).title(), round(float(m.group(2).replace(",", ".")) * 60)
    m = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(?:min(?:utos?)?)?\s*", value, re.I)
    return (None, round(float(m.group(1).replace(",", ".")) * 60)) if m else (None, None)


def logs():
    """Gera sessões por data e título, apenas linhas de registro real."""
    sessions = OrderedDict()
    for month in FILES:
        path = logs_dir() / "04-Logs e Aprendizados" / f"treinos-{month}-2026.md"
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8-sig")
        header = None
        for line in source.splitlines():
            if not line.lstrip().startswith("|"):
                # não continuar interpretando outras tabelas depois do registro diário
                continue
            cols = [s.strip() for s in line.strip().strip("|").split("|")]
            if cols and normalized(cols[0]) == "data" and len(cols) > 2 and "exerc" in normalized(cols[2]):
                header = [normalized(c) for c in cols]
                continue
            if header is None or not cols or not re.fullmatch(r"\d{1,2}/\d{1,2}", cols[0]):
                continue
            day, mon = map(int, cols[0].split("/"))
            try:
                session_date = date(2026, mon, day)
            except ValueError:
                raise ValueError(f"Data inválida em {path.name}: {cols[0]}")
            workout_title = cols[1].strip() if len(cols) > 1 else "Sem título"
            exercise = cols[2].strip() if len(cols) > 2 else ""
            if not workout_title or not exercise:
                continue
            keyed = {}
            for idx, key in enumerate(header):
                keyed[key] = cols[idx] if idx < len(cols) else ""
            # Linhas de alguns dias têm uma coluna a menos: preservar o texto deslocado.
            note_index = next((i for i, h in enumerate(header) if "notas" in h), len(header) - 1)
            notes = " | ".join(c for c in cols[note_index:] if c and c not in MISSING)
            if len(cols) < len(header):
                for piece in cols[7:]:
                    if piece not in MISSING and not re.fullmatch(r"\[.\]", piece) and piece not in notes:
                        if parse_cardio(piece)[1] is None:
                            notes = (notes + " | " + piece).strip(" |")
            weight = keyed.get("peso (kg)", "")
            reps = series(keyed.get("reps", ""))
            rpe = series(next((v for k, v in keyed.items() if k.startswith("rpe")), ""))
            rir = series(keyed.get("rir", ""))
            cardio_field = next((v for k, v in keyed.items() if k.startswith("cardio")), "")
            cardio_name, cardio_seconds = parse_cardio(cardio_field)
            if not cardio_seconds and len(cols) < len(header):
                for piece in cols[6:]:
                    name, secs = parse_cardio(piece)
                    if secs:
                        cardio_name, cardio_seconds = name, secs
                        break
            label = normalized(exercise)
            is_cardio = any(x in label for x in ("esteira", "bike", "bicicleta", "remo", "corda"))
            key = (session_date, workout_title)
            if key not in sessions:
                sessions[key] = []
            if reps or cardio_seconds:
                sessions[key].append({
                    "exercise": exercise, "weight": series(weight), "reps": reps,
                    "rpe": rpe, "rir": rir, "notes": notes,
                    "cardio_name": cardio_name, "cardio_seconds": cardio_seconds,
                    "is_cardio": is_cardio,
                })
    return {key: rows for key, rows in sessions.items() if rows}


def parsed_sets(row):
    result = []
    for i, raw_rep in enumerate(row["reps"]):
        duration_match = re.fullmatch(r"(\d+)\s*s", raw_rep, re.I)
        weight_text = repeats(row["weight"], i)
        weight, weight_note = parse_weight(weight_text)
        if duration_match:
            duration, reps = int(duration_match.group(1)), None
        else:
            duration, raw = None, number(raw_rep)
            reps = int(raw) if raw is not None and raw.is_integer() else None
        if reps is None and duration is None:
            continue
        notes = row["notes"]
        if weight_note:
            notes = f"{notes} | Peso original: {weight_note}".strip(" |")
        result.append({"weight_kg": weight, "reps": reps, "duration_seconds": duration,
                       "rpe": number(repeats(row["rpe"], i)),
                       "rir": number(repeats(row["rir"], i)), "notes": notes or None})
    return result
