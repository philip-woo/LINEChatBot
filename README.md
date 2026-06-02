# Factory Assistant

Ingests messages from **LINE** group/direct chats, stores them in **Postgres +
pgvector**, and answers natural-language questions about them with the **Claude
API**. Messages can be multilingual (Chinese / Japanese / English); Claude
translates and reasons across them at query time.

```
LINE → webhook (FastAPI) → embed → Postgres+pgvector ──(per question)──► Claude → answer
```

A Slack bot (separate, in progress) is the intended front-end; it just calls
`answer_question()` / `Conversation.ask()` from `app/claude_client.py`.

## Layout

| Path | Role |
|------|------|
| `app/main.py` | FastAPI app — LINE webhook at `POST /webhooks/line` (signature-verified) |
| `app/ingest/line.py` | Parse LINE events → normalize → store |
| `app/models.py` | Normalized message schema + persistence (insert/dedup, queries) |
| `app/embeddings.py` | Local multilingual embeddings (fastembed, 384-dim, no API key) |
| `app/retrieval.py` | Semantic search over pgvector (RAG) |
| `app/claude_client.py` | Claude answers: `answer_question` (RAG), `answer_question_simple` (feed-all), `Conversation` (ongoing chat) |
| `db/schema.sql` | Postgres schema (`messages` table + `vector(384)` + HNSW index) |
| `scripts/` | CLIs: `read`, `query`, `ask`, `chat`, `send_test_line` |

## Setup

Requires Python 3.10+, Postgres 16 with the `pgvector` extension.

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cp .env.example .env        # then fill in the values (see below)
createdb factory
./.venv/bin/python -m app.db   # applies db/schema.sql
```

### Environment (`.env`)

| Var | Purpose |
|-----|---------|
| `DATABASE_URL` | Postgres connection (e.g. `postgresql://localhost:5432/factory`) |
| `LINE_CHANNEL_SECRET` | LINE Messaging API channel secret (webhook signature) |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE token (resolves sender display names) |
| `ANTHROPIC_API_KEY` | Claude API key |
| `ANTHROPIC_MODEL` | defaults to `claude-opus-4-8` |
| `EMBED_MODEL` / `EMBED_DIM` | embedding model (default multilingual MiniLM, 384) |

`.env` is gitignored — never commit secrets.

## Run

```bash
./run.sh                                   # FastAPI ingestion service on :8000
# expose to LINE during dev:  cloudflared tunnel --url http://localhost:8000
#   → set the LINE webhook URL to  https://<tunnel>/webhooks/line
```

## Ask questions (CLIs)

```bash
./.venv/bin/python -m scripts.read                 # show stored messages
./.venv/bin/python -m scripts.query "defect"       # semantic search only
./.venv/bin/python -m scripts.ask "what's the connector issue?"        # RAG answer
./.venv/bin/python -m scripts.ask "summarize everything" --all          # feed-all answer
./.venv/bin/python -m scripts.chat                  # ongoing chat, fed new messages each turn
```

Scope any query to one chat with `--source line --chat-id <id>`.
