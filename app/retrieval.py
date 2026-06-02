"""Retrieval layer: semantic search over stored messages (pgvector cosine).

Embeds the query in the same space as stored passages and returns the top-k
nearest messages, optionally scoped by source, chat_id, and time range.
Never dumps the whole history — only the top-k go to Claude as context.
"""
from dataclasses import dataclass
from datetime import datetime

from .db import get_conn
from .embeddings import embed_query


@dataclass
class Hit:
    id: int
    source: str
    chat_id: str
    sender_name: str | None
    sender_id: str | None
    ts: datetime
    text: str
    score: float  # cosine similarity in [0,1], higher = closer


def search(
    query: str,
    *,
    k: int = 8,
    source: str | None = None,
    chat_id: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> list[Hit]:
    qvec = embed_query(query)

    where = ["embedding IS NOT NULL"]
    params: list = []
    if source:
        where.append("source = %s")
        params.append(source)
    if chat_id:
        where.append("chat_id = %s")
        params.append(chat_id)
    if since:
        where.append("ts >= %s")
        params.append(since)
    if until:
        where.append("ts <= %s")
        params.append(until)
    where_sql = " AND ".join(where)

    # 1 - cosine_distance = cosine_similarity
    sql = f"""
        SELECT id, source, chat_id, sender_name, sender_id, ts, text,
               1 - (embedding <=> %s::vector) AS score
        FROM messages
        WHERE {where_sql}
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    args = [qvec, *params, qvec, k]
    with get_conn() as conn:
        cur = conn.execute(sql, args)
        rows = cur.fetchall()

    return [
        Hit(id=r[0], source=r[1], chat_id=r[2], sender_name=r[3],
            sender_id=r[4], ts=r[5], text=r[6], score=float(r[7]))
        for r in rows
    ]
