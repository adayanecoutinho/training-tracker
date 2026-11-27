"""Autorização única do Strava no navegador padrão."""
import secrets
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlencode, urlsplit, parse_qs

from strava_client import credentials, exchange


def main():
    client_id, _ = credentials()
    state = secrets.token_urlsafe(32)
    result = {}

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # A URL contém um código confidencial.

        def do_GET(self):
            query = parse_qs(urlsplit(self.path).query)
            valid = (urlsplit(self.path).path == '/callback' and
                     secrets.compare_digest(query.get('state', [''])[0], state))
            if not valid:
                self.send_response(400)
                self.end_headers()
                return
            if query.get('error') or 'code' not in query:
                result['error'] = 'Autorização recusada.'
            elif 'activity:read_all' not in query.get('scope', [''])[0].split(','):
                result['error'] = 'É necessário permitir activity:read_all. Execute novamente.'
            else:
                result['code'] = query['code'][0]
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write('Resposta recebida. Pode fechar esta aba e voltar ao Codex.'.encode())

    with HTTPServer(('127.0.0.1', 0), Callback) as server:
        server.timeout = 1
        url = 'https://www.strava.com/oauth/authorize?' + urlencode(dict(
            client_id=client_id, redirect_uri=f'http://localhost:{server.server_port}/callback',
            response_type='code', approval_prompt='force', scope='activity:read_all', state=state))
        print('No navegador: entre no Strava, permita ler todas as atividades e clique em Autorizar.', flush=True)
        if not webbrowser.open(url):
            raise SystemExit('Não foi possível abrir o navegador padrão. Execute num terminal local.')
        deadline = time.monotonic() + 900
        while not result and time.monotonic() < deadline:
            server.handle_request()
    if not result:
        raise SystemExit('Prazo de autorização expirou. Execute novamente.')
    if 'error' in result:
        raise SystemExit(result['error'])
    exchange(grant_type='authorization_code', code=result['code'])
    print('Autorização concluída; tokens salvos apenas em data/strava_tokens.json.')


if __name__ == '__main__':
    main()
