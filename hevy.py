"""Cliente mínimo da Hevy Public API (https://api.hevyapp.com/docs).

Só usa a stdlib. A chave vem de HEVY_API_KEY no arquivo .env ao lado deste script.
"""

import json
import os
import urllib.parse
import urllib.request

from env import ROOT, load_env  # noqa: F401  (ROOT e load_env reexportados)

BASE_URL = "https://api.hevyapp.com"


def api_key() -> str:
    load_env()
    key = os.environ.get("HEVY_API_KEY", "")
    if not key:
        raise SystemExit("HEVY_API_KEY não encontrada. Copie .env.example para .env e preencha.")
    return key


def get(path: str, **params) -> dict:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{BASE_URL}{path}" + (f"?{query}" if query else "")
    req = urllib.request.Request(url, headers={"api-key": api_key(), "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def paginate(path: str, items_key: str, page_size: int = 10, **params):
    """Percorre todas as páginas de um endpoint paginado."""
    page = 1
    while True:
        data = get(path, page=page, pageSize=page_size, **params)
        yield from data.get(items_key, [])
        if page >= int(data.get("page_count", 1)):
            break
        page += 1
