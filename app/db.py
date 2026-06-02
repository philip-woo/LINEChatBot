"""Postgres connection pool + helpers, with pgvector registered."""
import os
from contextlib import contextmanager

from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector

from .config import settings

_pool: ConnectionPool | None = None


def _configure(conn):
    register_vector(conn)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            settings.DATABASE_URL,
            min_size=1,
            max_size=10,
            configure=_configure,
            open=True,
        )
    return _pool


@contextmanager
def get_conn():
    with get_pool().connection() as conn:
        yield conn


def init_db():
    """Run db/schema.sql (idempotent: extension, table, indexes)."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "db", "schema.sql")
    with open(schema_path, "r") as f:
        sql = f.read()
    with get_conn() as conn:
        conn.execute(sql)
        conn.commit()


if __name__ == "__main__":
    init_db()
    print("Schema applied.")
