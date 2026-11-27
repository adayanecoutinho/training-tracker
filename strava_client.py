"""Strava somente leitura; tokens locais e respostas nunca são logados."""
import json
import os
import time
from datetime import datetime, timezone
from urllib import request, parse, error

from hevy import ROOT, load_env

TOKENS = ROOT / 'data' / 'strava_tokens.json'


def credentials():
    load_env()
    values = tuple(os.environ.get(k, '').strip() for k in
                   ('STRAVA_CLIENT_ID', 'STRAVA_CLIENT_SECRET'))
    if not all(values):
        raise SystemExit('Preencha STRAVA_CLIENT_ID e STRAVA_CLIENT_SECRET no .env.')
    return values


def save_tokens(data):
    # Não persistir o objeto athlete, que pode conter localização.
    selected = {k: data[k] for k in ('access_token', 'refresh_token', 'expires_at')}
    TOKENS.parent.mkdir(exist_ok=True)
    temp = TOKENS.with_suffix('.tmp')
    # Cria já com permissão 600: o padrão do sistema deixaria o arquivo legível por outros.
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as handle:
        handle.write(json.dumps(selected))
    temp.replace(TOKENS)


def exchange(**params):
    client_id, secret = credentials()
    body = parse.urlencode(dict(client_id=client_id, client_secret=secret, **params)).encode()
    req = request.Request('https://www.strava.com/oauth/token', data=body)
    try:
        with request.urlopen(req, timeout=30) as response:
            data = json.load(response)
    except error.HTTPError as exc:
        raise RuntimeError(f'Falha na autorização Strava (HTTP {exc.code}).') from None
    save_tokens(data)
    return data


def pause(seconds):
    remaining = max(1, int(seconds))
    print(f'Limite Strava: aguardando {remaining} segundos para retomar.', flush=True)
    while remaining:
        step = min(30, remaining)
        time.sleep(step)
        remaining -= step


def rate_wait(headers, limited=False):
    now = time.time()
    wait = 0
    for prefix in ('X-RateLimit', 'X-ReadRateLimit'):
        try:
            limits = list(map(int, headers.get(prefix + '-Limit', '100,1000').split(',')))
            usage = list(map(int, headers.get(prefix + '-Usage', '0,0').split(',')))
            if usage[0] >= min(limits[0], 100):
                wait = max(wait, 900 - now % 900 + 2)
            if usage[1] >= min(limits[1], 1000):
                wait = max(wait, 86400 - now % 86400 + 2)
        except (ValueError, IndexError):
            pass
    if limited:
        try:
            retry = float(headers.get('Retry-After', 0))
        except ValueError:
            retry = 0
        wait = max(wait, retry, 900 - now % 900 + 2)
    return wait


class Client:
    def __init__(self):
        self.ready_at = 0

    def get(self, path, **params):
        while True:
            if time.time() < self.ready_at:
                pause(self.ready_at - time.time())
            if not TOKENS.exists():
                raise SystemExit('Execute python strava_auth.py primeiro.')
            tokens = json.loads(TOKENS.read_text(encoding='utf-8'))
            if tokens['expires_at'] - time.time() < 300:
                tokens = exchange(grant_type='refresh_token', refresh_token=tokens['refresh_token'])
            url = 'https://www.strava.com/api/v3' + path
            if params:
                url += '?' + parse.urlencode(params)
            req = request.Request(url, headers={'Authorization': 'Bearer ' + tokens['access_token']})
            try:
                with request.urlopen(req, timeout=30) as response:
                    self.ready_at = time.time() + rate_wait(response.headers)
                    return json.load(response)
            except error.HTTPError as exc:
                if exc.code == 429:
                    self.ready_at = time.time() + rate_wait(exc.headers, limited=True)
                    continue
                raise RuntimeError(f'Falha na consulta Strava (HTTP {exc.code}).') from None
