"""Executa uma tarefa agendada e avisa o Healthchecks.io (início, sucesso ou falha).

Uso: python job.py sync | relatorio

A URL de ping é segredo: vem só de variável de ambiente e nunca é impressa.
Falha ao avisar o Healthchecks não derruba a tarefa; falha da tarefa vira o código
de saída e um aviso /fail sem o texto da saída (ela fica nos logs do agendador).
"""

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

JOBS = {
    "sync": ("HEALTHCHECK_URL_SYNC", [["sync.py"], ["sync_strava.py"]]),
    "relatorio": ("HEALTHCHECK_URL_RELATORIO", [["report.py", "--weeks", "8"], ["load_steps.py"]]),
}


def ping(base, suffix="", body=None):
    if not base:
        return
    url = base.rstrip("/") + suffix
    data = body.encode("utf-8") if body else None
    for _ in range(3):
        try:
            request = urllib.request.Request(url, data=data, method="POST" if data else "GET")
            with urllib.request.urlopen(request, timeout=10):
                return
        except (urllib.error.URLError, OSError):
            time.sleep(2)
    # Sem detalhes do erro: a mensagem poderia conter a URL secreta.
    print("aviso: não consegui avisar o Healthchecks", file=sys.stderr)


def run(name, runner=subprocess.run):
    env_var, steps = JOBS[name]
    base = os.environ.get(env_var, "").strip()
    if not base:
        print(f"aviso: {env_var} não definida; sem aviso ao Healthchecks", file=sys.stderr)
    ping(base, "/start")
    for step in steps:
        print(f"[{name}] python {' '.join(step)}", flush=True)
        result = runner([sys.executable, *step])
        if result.returncode != 0:
            ping(base, "/fail", f"{name}: {step[0]} terminou com código {result.returncode}")
            return result.returncode or 1
    ping(base)
    return 0


def main(argv):
    if len(argv) != 2 or argv[1] not in JOBS:
        print(f"uso: python job.py {{{' | '.join(JOBS)}}}", file=sys.stderr)
        return 2
    return run(argv[1])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
