"""Carrega o .env ao lado dos scripts para os.environ (só stdlib).

Valores já definidos no ambiente têm prioridade sobre o arquivo.
"""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load_env() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
