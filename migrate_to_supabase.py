"""Copia registros do Postgres isolado para o Supabase local, preservando IDs.

O banco de origem é aberto somente para leitura; a cópia inteira é transacional.
Reexecuções preservam registros já presentes no destino, inclusive o cursor
de sincronização que pode ter avançado após a primeira migração.
"""

import os

import psycopg
from psycopg import sql


SOURCE = os.environ.get(
    "SOURCE_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:57322/postgres"
)
TARGET = os.environ.get(
    "TARGET_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:58322/postgres"
)

# Ordem que respeita referências entre tabelas.
TABLES = {
    "exercises": ("id",),
    "workouts": ("id",),
    "sets": ("id",),
    "body_metrics": ("date",),
    "daily_checkins": ("date",),
    "mesocycles": ("id",),
    "mesocycle_weeks": ("mesocycle_id", "week_number"),
    "sync_state": ("key",),
    "exercise_hevy_templates": ("template_id",),
}


def columns(conn, table):
    return [
        row[0]
        for row in conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            (table,),
        )
    ]


def migrate():
    with psycopg.connect(SOURCE) as source, psycopg.connect(TARGET) as target:
        source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        if source.info.host == target.info.host and source.info.port == target.info.port:
            raise ValueError("Origem e destino apontam para o mesmo servidor")
        for table, primary_key in TABLES.items():
            names = columns(source, table)
            if not names or names != columns(target, table):
                raise ValueError(f"Estrutura incompatível para a tabela {table}")
            identifiers = sql.SQL(", ").join(map(sql.Identifier, names))
            keys = sql.SQL(", ").join(map(sql.Identifier, primary_key))
            staging = sql.Identifier("staging_" + table)
            table_id = sql.Identifier(table)
            target.execute(
                sql.SQL("CREATE TEMP TABLE {} (LIKE public.{}) ON COMMIT DROP").format(
                    staging, table_id
                )
            )
            with source.cursor() as scur, target.cursor() as tcur:
                with scur.copy(
                    sql.SQL("COPY public.{} ({}) TO STDOUT").format(table_id, identifiers)
                ) as reader:
                    with tcur.copy(
                        sql.SQL("COPY {} ({}) FROM STDIN").format(staging, identifiers)
                    ) as writer:
                        for chunk in reader:
                            writer.write(chunk)
            target.execute(
                sql.SQL("INSERT INTO public.{} ({}) SELECT {} FROM {} WHERE TRUE "
                        "ON CONFLICT ({}) DO NOTHING").format(
                    table_id, identifiers, identifiers, staging, keys
                )
            )
            expected = source.execute(
                sql.SQL("SELECT count(*) FROM public.{}").format(table_id)
            ).fetchone()[0]
            actual = target.execute(
                sql.SQL("SELECT count(*) FROM public.{}").format(table_id)
            ).fetchone()[0]
            if expected != actual:
                raise ValueError(f"{table}: origem={expected}, destino={actual}")
            print(f"{table}: {actual} registros conferidos")
    print("Cópia concluída e commit realizado no Supabase local.")


if __name__ == "__main__":
    migrate()
