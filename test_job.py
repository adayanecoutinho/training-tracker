"""Testes do executor de tarefas agendadas, sem rede."""

import contextlib
import io
import os
import unittest
import urllib.error
from types import SimpleNamespace
from unittest.mock import patch

import job

URL = "https://hc-ping.example/test"


class FakeRunner:
    def __init__(self, fail_on=None):
        self.calls, self.fail_on = [], fail_on

    def __call__(self, cmd):
        self.calls.append(cmd[1:])
        failed = self.fail_on and cmd[1] == self.fail_on
        return SimpleNamespace(returncode=3 if failed else 0)


class JobTests(unittest.TestCase):
    def setUp(self):
        self.pings = []
        patcher = patch.object(job, "ping", lambda base, suffix="", body=None:
                               self.pings.append((base, suffix, body)))
        patcher.start()
        self.addCleanup(patcher.stop)
        env = patch.dict(os.environ, {"HEALTHCHECK_URL_SYNC": URL}, clear=False)
        env.start()
        self.addCleanup(env.stop)

    def test_success_runs_all_steps_and_pings_start_then_success(self):
        runner = FakeRunner()
        self.assertEqual(job.run("sync", runner), 0)
        self.assertEqual(runner.calls, [["sync.py"], ["sync_strava.py"]])
        self.assertEqual([s for _, s, _ in self.pings], ["/start", ""])

    def test_failure_stops_and_pings_fail_without_output(self):
        runner = FakeRunner(fail_on="sync.py")
        self.assertEqual(job.run("sync", runner), 3)
        self.assertEqual(runner.calls, [["sync.py"]])
        self.assertEqual([s for _, s, _ in self.pings], ["/start", "/fail"])
        self.assertIn("sync.py", self.pings[-1][2])
        self.assertNotIn(URL, self.pings[-1][2])

    def test_report_job_uses_its_own_variable(self):
        with patch.dict(os.environ, {"HEALTHCHECK_URL_RELATORIO": "https://hc-ping.example/report"}):
            runner = FakeRunner()
            self.assertEqual(job.run("relatorio", runner), 0)
        self.assertEqual(runner.calls, [["report.py", "--weeks", "8"], ["load_steps.py"]])
        self.assertEqual(self.pings[0][0], "https://hc-ping.example/report")

    def test_missing_url_still_runs_the_job(self):
        with patch.dict(os.environ, {"HEALTHCHECK_URL_SYNC": ""}):
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(job.run("sync", FakeRunner()), 0)
        self.assertIn("HEALTHCHECK_URL_SYNC", err.getvalue())
        self.assertNotIn(URL, err.getvalue())

    def test_unknown_job_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(job.main(["job.py", "outra"]), 2)
            self.assertEqual(job.main(["job.py"]), 2)


class PingTests(unittest.TestCase):
    def test_ping_failure_never_leaks_the_url(self):
        err = io.StringIO()
        boom = urllib.error.URLError(f"falha em {URL}")
        with patch("urllib.request.urlopen", side_effect=boom), \
                patch("time.sleep"), contextlib.redirect_stderr(err):
            job.ping(URL, "/start")
        self.assertIn("não consegui avisar", err.getvalue())
        self.assertNotIn("hc-ping.example", err.getvalue())

    def test_ping_uses_suffix_and_post_for_body(self):
        seen = []

        def fake(request, timeout):
            seen.append((request.full_url, request.get_method()))
            return contextlib.nullcontext()

        with patch("urllib.request.urlopen", fake):
            job.ping(URL + "/", "/fail", "texto")
            job.ping(URL)
        self.assertEqual(seen, [(URL + "/fail", "POST"), (URL, "GET")])


if __name__ == "__main__":
    unittest.main()
