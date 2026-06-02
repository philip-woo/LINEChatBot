-- Factory assistant schema: raw + normalized messages with pgvector embeddings.
-- Embedding dimension (384) matches the default model intfloat/multilingual-e5-small.
-- If you change EMBED_MODEL/EMBED_DIM, change vector(384) below to match.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS messages (
    id                BIGSERIAL PRIMARY KEY,
    source            TEXT        NOT NULL,                 -- 'line' | 'wechat'
    chat_id           TEXT        NOT NULL,                 -- conversation id (group/room/user)
    sender_id         TEXT,                                 -- platform user id
    sender_name       TEXT,                                 -- resolved display name
    ts                TIMESTAMPTZ NOT NULL,                 -- message timestamp (from platform)
    text              TEXT,                                 -- message body (original language)
    attachments       JSONB       NOT NULL DEFAULT '[]'::jsonb,
    source_message_id TEXT,                                 -- platform message id (for dedup)
    raw               JSONB,                                -- full raw event, for provenance/debug
    received_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    embedding         vector(384),                          -- nullable until computed
    UNIQUE (source, source_message_id)
);

-- Fast filtering by conversation + time (used by retrieval scoping).
CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages (source, chat_id, ts DESC);
CREATE INDEX IF NOT EXISTS idx_messages_ts   ON messages (ts DESC);

-- Approximate nearest-neighbour index for semantic search (cosine distance).
-- HNSW suits small/medium data and needs no training step.
CREATE INDEX IF NOT EXISTS idx_messages_embedding
    ON messages USING hnsw (embedding vector_cosine_ops);
