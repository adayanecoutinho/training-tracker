"""Conexão ao Postgres. DATABASE_URL (ambiente ou .env) define o banco."""

import os

import psycopg

from env import load_env


def connect():
    load_env()
    return psycopg.connect(
        os.environ.get(
            "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:58322/postgres"
        )
    )
