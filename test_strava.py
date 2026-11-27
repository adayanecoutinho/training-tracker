"""Testes sem rede de filtragem, renovação de tokens e limites."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import strava_client as sc
from sync_strava import is_hevy

(sc.ROOT / 'data').mkdir(exist_ok=True)


class StravaTests(unittest.TestCase):
    def test_filter(self):
        self.assertTrue(is_hevy({'sport_type': 'WeightTraining'}))
        self.assertTrue(is_hevy({'sport_type': 'Walk', 'description': 'Registrado com hevyapp.com xxx'}))
        self.assertFalse(is_hevy({'sport_type': 'Walk', 'description': None}))

    def test_token_file_excludes_athlete(self):
        with tempfile.TemporaryDirectory(dir=sc.ROOT / 'data') as tmp, patch.object(sc, 'TOKENS', Path(tmp)/'tokens.json'):
            sc.save_tokens(dict(access_token='fake', refresh_token='fake2', expires_at=10,
                                athlete={'city': 'private'}))
            self.assertEqual(set(json.loads(sc.TOKENS.read_text())),
                             {'access_token', 'refresh_token', 'expires_at'})

    @unittest.skipIf(os.name == 'nt', 'permissões POSIX não se aplicam no Windows')
    def test_token_file_is_private(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'strava_tokens.json'
            with patch.object(sc, 'TOKENS', path):
                old = os.umask(0o022)
                try:
                    sc.save_tokens({'access_token': 'a', 'refresh_token': 'b', 'expires_at': 1})
                finally:
                    os.umask(old)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_daily_and_quarter_limits(self):
        with patch.object(sc.time, 'time', return_value=100):
            self.assertEqual(sc.rate_wait({'X-ReadRateLimit-Usage': '100,100'}), 802)
            self.assertEqual(sc.rate_wait({'X-ReadRateLimit-Usage': '1,1000'}), 86302)
            self.assertEqual(sc.rate_wait({}, limited=True), 802)

    def test_refresh_before_request(self):
        with tempfile.TemporaryDirectory(dir=sc.ROOT / 'data') as tmp, patch.object(sc, 'TOKENS', Path(tmp)/'tokens.json'):
            sc.save_tokens(dict(access_token='old', refresh_token='refresh', expires_at=101))
            response = unittest.mock.MagicMock()
            response.__enter__.return_value.read.return_value = b'[]'
            response.__enter__.return_value.headers = {}
            with patch.object(sc.time, 'time', return_value=100), patch.object(
                    sc, 'exchange', return_value={'access_token': 'new'}) as exchange, patch.object(
                    sc.request, 'urlopen', return_value=response) as open_url:
                self.assertEqual(sc.Client().get('/athlete/activities'), [])
                exchange.assert_called_once_with(grant_type='refresh_token', refresh_token='refresh')
                self.assertEqual(open_url.call_args.args[0].get_header('Authorization'), 'Bearer new')


if __name__ == '__main__':
    unittest.main()
