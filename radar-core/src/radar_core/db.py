import sqlite3

from sqlalchemy import Engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.pool import ConnectionPoolEntry
from sqlmodel import Session, create_engine


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(
    dbapi_connection: DBAPIConnection, connection_record: ConnectionPoolEntry
) -> None:
    """Enforce foreign-key constraints on every new SQLite connection.

    SQLite disables FK enforcement by default for backward compatibility, so
    without this pragma a row referencing a nonexistent parent row inserts
    silently instead of raising `IntegrityError`. No-op for non-SQLite
    connections (e.g. a future Postgres backend), which enforce FKs natively.
    """
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_engine(database_url: str) -> Engine:
    return create_engine(database_url)


def get_session(engine: Engine) -> Session:
    return Session(engine)
