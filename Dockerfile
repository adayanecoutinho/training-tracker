# Imagem do treino-evolucao: sem porta, os scripts rodam como tarefas agendadas
# (docker exec) e o processo principal só mantém o container vivo.
FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd --uid 10001 --no-create-home treino \
    && mkdir -p data/raw reports \
    && chown -R treino /app/data /app/reports
USER treino

# Saudável = Python e dependências carregam. Não testa o banco de propósito:
# uma queda do Postgres não deve deixar este container unhealthy.
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD python -c "import psycopg, db, hevy, strava_client" || exit 1

# Fica parado esperando as tarefas; sai limpo no SIGTERM do redeploy.
CMD ["sh", "-c", "trap 'exit 0' TERM INT; while :; do sleep 3600 & wait $!; done"]
