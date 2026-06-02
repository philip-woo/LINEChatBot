"""Normalized message schema + persistence (insert with dedup + embedding)."""
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .db import get_conn
from .embeddings import embed_passage


@dataclass
class NormalizedMessage:
    source: str                      # 'line' | 'wechat'
    chat_id: str                     # conversation id
    sender_id: str | None
    sender_name: str | None
    timestamp: datetime              # message time (tz-aware)
    text: str | None
    source_message_id: str | None    # platform id, for dedup
    attachments: list[dict] = field(default_factory=list)
    raw: dict[str, Any] | None = None


def save_message(msg: NormalizedMessage) -> int | None:
    """Insert a message (embedding computed for non-empty text).

    Returns the new row id, or None if it was a duplicate (same source +
    source_message_id) and therefore skipped.
    """
    embedding = embed_passage(msg.text) if msg.text else None
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO messages
                (source, chat_id, sender_id, sender_name, ts, text,
                 attachments, source_message_id, raw, embedding)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (source, source_message_id) DO NOTHING
            RETURNING id
            """,
            (
                msg.source,
                msg.chat_id,
                msg.sender_id,
                msg.sender_name,
                msg.timestamp,
                msg.text,
                json.dumps(msg.attachments),
                msg.source_message_id,
                json.dumps(msg.raw) if msg.raw is not None else None,
                embedding,
            ),
        )
        row = cur.fetchone()
        conn.commit()
    return row[0] if row else None


def all_messages(
    source: str | None = None,
    chat_id: str | None = None,
    limit: int = 5000,
) -> list[dict]:
    """All stored messages in chronological order (oldest first), optionally scoped.

    Used by the 'feed everything' answer mode — no retrieval, just dump them.
    """
    where, params = [], []
    if source:
        where.append("source = %s")
        params.append(source)
    if chat_id:
        where.append("chat_id = %s")
        params.append(chat_id)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    with get_conn() as conn:
        cur = conn.execute(
            f"""
            SELECT id, source, chat_id, sender_id, sender_name, ts, text
            FROM messages {where_sql} ORDER BY ts ASC LIMIT %s
            """,
            (*params, limit),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def messages_after(
    after_id: int = 0,
    source: str | None = None,
    chat_id: str | None = None,
    limit: int = 5000,
) -> list[dict]:
    """Messages with id > after_id (i.e. arrived since), chronological, optionally scoped.

    Used by the ongoing Conversation to inject only NEW messages each turn.
    """
    where, params = ["id > %s"], [after_id]
    if source:
        where.append("source = %s")
        params.append(source)
    if chat_id:
        where.append("chat_id = %s")
        params.append(chat_id)
    where_sql = "WHERE " + " AND ".join(where)
    with get_conn() as conn:
        cur = conn.execute(
            f"""
            SELECT id, source, chat_id, sender_id, sender_name, ts, text
            FROM messages {where_sql} ORDER BY id ASC LIMIT %s
            """,
            (*params, limit),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def recent_messages(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, source, chat_id, sender_id, sender_name, ts, text
            FROM messages ORDER BY ts DESC LIMIT %s
            """,
            (limit,),
        )
        cols = [c.name for c in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
