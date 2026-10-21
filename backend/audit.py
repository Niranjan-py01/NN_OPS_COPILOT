
import json
import logging
import os
import threading
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .config import DATABASE_URL

logger = logging.getLogger(__name__)

# PostgreSQL connection
_engine = None
_table_ready = False
_table_lock = threading.Lock()

if DATABASE_URL:
    try:
        _engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            future=True,
        )
    except Exception:
        logger.exception(
            "Could not initialize PostgreSQL audit engine."
        )


def _ensure_audit_table(conn):
    """Create the audit table once per application process."""
    global _table_ready

    if _table_ready:
        return

    with _table_lock:
        if _table_ready:
            return

        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    detail JSONB NOT NULL
                )
                """
            )
        )

        _table_ready = True


def _write_fallback(event_type, actor, detail):
    """Write an audit event to a local JSONL file."""
    event = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "actor": actor,
        "detail": detail,
    }

    try:
        os.makedirs("data", exist_ok=True)

        with open(
            os.path.join("data", "audit_fallback.jsonl"),
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(event, ensure_ascii=False) + "\n"
            )

    except (OSError, TypeError, ValueError):
        logger.exception("Local audit fallback write failed.")
        raise


def audit_event(event_type: str, actor: str, detail: dict):
    """
    Persist an audit event in PostgreSQL.

    If PostgreSQL is unavailable, use the local JSONL fallback.
    Raise an exception if neither storage method succeeds.
    """
    # Validate that the detail can be represented as JSON.
    serialized_detail = json.dumps(detail, ensure_ascii=False)

    if _engine is not None:
        try:
            with _engine.begin() as conn:
                _ensure_audit_table(conn)

                conn.execute(
                    text(
                        """
                        INSERT INTO audit_events
                            (event_type, actor, detail)
                        VALUES
                            (:event_type, :actor, CAST(:detail AS JSONB))
                        """
                    ),
                    {
                        "event_type": event_type,
                        "actor": actor,
                        "detail": serialized_detail,
                    },
                )

            return

        except SQLAlchemyError:
            logger.exception(
                "PostgreSQL audit write failed; trying local fallback."
            )

    try:
        _write_fallback(event_type, actor, detail)
    except Exception as exc:
        raise RuntimeError(
            "Could not persist the audit event to PostgreSQL "
            "or the local fallback file."
        ) from exc
