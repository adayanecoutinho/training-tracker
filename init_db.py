"""Aplica migrations ao Postgres local isolado quando Supabase CLI não inicia."""

from pathlib import Path

from db import connect

MIGRATIONS = Path(__file__).resolve().parent / "supabase" / "migrations"


def run():
    with connect() as conn:
        with conn.transaction():
            conn.execute(
                "CREATE TABLE IF NOT EXISTS local_schema_migrations "
                "(filename text PRIMARY KEY, applied_at timestamptz DEFAULT now())"
            )
        for sql_file in sorted(MIGRATIONS.glob("*.sql")):
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM local_schema_migrations WHERE filename=%s",
                                (sql_file.name,))
                    if cur.fetchone():
                        continue
                    cur.execute(sql_file.read_text(encoding="utf-8"), prepare=False)
                    cur.execute("INSERT INTO local_schema_migrations(filename) VALUES (%s)",
                                (sql_file.name,))
                    print(f"Migration aplicada: {sql_file.name}")


if __name__ == "__main__":
    run()
