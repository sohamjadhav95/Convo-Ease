"""
ConvoEase - Database Manager
Table definitions and connection handling.

The app talks to the database through SQLAlchemy Core, so the same code runs on
a local SQLite file (default) and on hosted Postgres (set DATABASE_URL).
"""

import threading
import time
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    Index,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
    inspect,
    text,
)

import config
from config import setup_logging

logger = setup_logging("db_manager")

metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("username", String(64), primary_key=True),
    Column("password", String(255), nullable=False),
    Column("full_name", String(120), nullable=False, default=""),
    Column("bio", Text, nullable=False, default=""),
    Column("profile_pic_color", String(16), nullable=False, default=""),
    Column("avatar", String(32), nullable=False, default=""),
    Column("created_at", String(19), nullable=False),
)

chat_groups = Table(
    "chat_groups",
    metadata,
    Column("group_id", String(16), primary_key=True),
    Column("group_name", String(120), nullable=False),
    Column("admin_username", String(64), nullable=False),
    Column("password", String(255), nullable=False, default=""),
    Column("rules", Text, nullable=False, default=""),
    Column("moderation_sensitivity", String(16), nullable=False, default="Moderate"),
    Column("created_at", String(19), nullable=False),
)

group_members = Table(
    "group_members",
    metadata,
    Column("group_id", String(16), primary_key=True),
    Column("username", String(64), primary_key=True),
    Column("joined_at", String(19), nullable=False),
    # Highest message seq this member has seen; drives unread counts.
    Column("last_read_seq", Integer, nullable=False, default=0),
)

messages = Table(
    "messages",
    metadata,
    # seq gives a stable order even when two messages share a timestamp.
    Column("seq", Integer, primary_key=True, autoincrement=True),
    Column("message_id", String(36), nullable=False, unique=True),
    Column("group_id", String(16), nullable=False),
    Column("username", String(64), nullable=False),
    Column("message", Text, nullable=False, default=""),
    Column("status", String(16), nullable=False),
    Column("reason", Text, nullable=False, default=""),
    Column("summary", Text, nullable=False, default=""),
    Column("media_url", String(255), nullable=False, default=""),
    Column("group_rules", Text, nullable=False, default=""),
    Column("timestamp", String(19), nullable=False),
    Column("initial_status", String(16), nullable=False, default=""),
    Column("initial_reason", Text, nullable=False, default=""),
    Column("detected_language", String(16), nullable=False, default=""),
    Column("language_confidence", String(16), nullable=False, default=""),
    Column("translated_message", Text, nullable=False, default=""),
    Column("appeal_status", String(16), nullable=False, default=""),
    Column("appeal_text", Text, nullable=False, default=""),
    Column("appeal_ai_status", String(16), nullable=False, default=""),
    Column("appeal_ai_reason", Text, nullable=False, default=""),
    Column("appeal_submitted_at", String(19), nullable=False, default=""),
    Column("appeal_reviewed_by", String(64), nullable=False, default=""),
    Column("appeal_reviewed_at", String(19), nullable=False, default=""),
    Column("appeal_admin_note", Text, nullable=False, default=""),
    Index("ix_messages_group_seq", "group_id", "seq"),
)

media = Table(
    "media",
    metadata,
    Column("media_id", String(64), primary_key=True),  # "<uuid>.<ext>"
    Column("kind", String(8), nullable=False),  # image | audio
    Column("group_id", String(16), nullable=False, index=True),
    Column("username", String(64), nullable=False),
    Column("mime_type", String(64), nullable=False),
    Column("size", Integer, nullable=False),
    Column("data", LargeBinary, nullable=False),
    Column("created_at", String(19), nullable=False),
)

MESSAGE_COLUMNS = [c.name for c in messages.columns]


def utc_now():
    """Timestamps are stored in UTC as 'YYYY-MM-DD HH:MM:SS'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def normalize_database_url(url):
    url = (url or "").strip()
    # Many hosts hand out postgres:// URLs; SQLAlchemy wants an explicit driver.
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


_engine = None
_engine_lock = threading.Lock()


def _create_engine(url):
    if url.startswith("sqlite"):
        engine = create_engine(
            url,
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

        return engine

    # Hosted Postgres drops idle connections, so check them before use.
    # prepare_threshold=None turns off server-side prepared statements, which
    # break behind transaction poolers such as Neon's or Supabase's.
    return create_engine(
        url,
        connect_args={"prepare_threshold": None},
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=5,
    )


class DBManager:
    """Creates the engine and the tables."""

    @staticmethod
    def initialize(database_url=None):
        """Connect to the database and create any missing tables."""
        global _engine
        url = normalize_database_url(database_url or config.DATABASE_URL)
        with _engine_lock:
            if _engine is not None:
                _engine.dispose()
            _engine = _create_engine(url)
            DBManager._create_schema(_engine)
        logger.info("Database ready (%s)", url.split("://", 1)[0])
        return _engine

    @staticmethod
    def _create_schema(engine, attempts=3):
        # Several server workers may start at once against a fresh database;
        # if another one wins the race to create a table, just try again.
        for attempt in range(1, attempts + 1):
            try:
                metadata.create_all(engine)
                DBManager._add_missing_columns(engine)
                return
            except Exception as exc:
                if attempt == attempts:
                    raise
                logger.warning("Schema setup retry %d after: %s", attempt, exc)
                time.sleep(0.5 * attempt)

    @staticmethod
    def engine():
        if _engine is None:
            DBManager.initialize()
        return _engine

    @staticmethod
    def _add_missing_columns(engine):
        """Tiny forward-only migration: add columns that newer code expects."""
        inspector = inspect(engine)
        for table in metadata.sorted_tables:
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                col_type = column.type.compile(dialect=engine.dialect)
                default = "0" if isinstance(column.type, Integer) else "''"
                with engine.begin() as conn:
                    conn.execute(text(
                        f'ALTER TABLE {table.name} ADD COLUMN "{column.name}" {col_type} '
                        f"NOT NULL DEFAULT {default}"
                    ))
                logger.info("Added column %s.%s", table.name, column.name)

    @staticmethod
    def fetch_all(statement):
        with DBManager.engine().connect() as conn:
            return [dict(row._mapping) for row in conn.execute(statement)]

    @staticmethod
    def fetch_one(statement):
        with DBManager.engine().connect() as conn:
            row = conn.execute(statement).first()
            return dict(row._mapping) if row is not None else None

    @staticmethod
    def scalar(statement):
        with DBManager.engine().connect() as conn:
            return conn.execute(statement).scalar()

    @staticmethod
    def execute(statement):
        with DBManager.engine().begin() as conn:
            return conn.execute(statement)

    @staticmethod
    def begin():
        """Transaction context manager for multi-statement writes."""
        return DBManager.engine().begin()
