"""Claude integration: answer questions over retrieved factory-floor messages.

RAG + tool-use loop:
  1. Retrieve top-k messages for the question (app.retrieval.search).
  2. Send them to Claude as context alongside the question.
  3. Expose a `search_messages` tool so Claude can pull MORE context itself
     if the first retrieval is thin (proper agentic tool-use loop).

Messages may be in Chinese/Japanese while the question is English — Claude
handles cross-lingual reasoning and translation.

Model + key come from app.config.settings (ANTHROPIC_API_KEY, ANTHROPIC_MODEL).
Prompt caching is applied to the stable system+tools prefix.
"""
import logging

import anthropic

from .config import settings
from .retrieval import search, Hit
from .models import all_messages, messages_after

log = logging.getLogger("claude_client")

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # api_key omitted → SDK reads ANTHROPIC_API_KEY from env; pass explicitly
        # when settings carries it so .env-loaded keys work too.
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY or None)
    return _client


SYSTEM_PROMPT = """You are the Factory Floor Assistant, a production-engineering \
helper for a manufacturing operations team. You answer questions from engineers \
and managers about what has been discussed across the team's LINE and WeChat \
group chats.

You are given a set of retrieved chat messages as context. Each message is shown as:
  [#id | timestamp | sender | source/chat] text

Guidelines:
- Answer ONLY from the provided messages and anything you retrieve via the \
search_messages tool. Do not invent facts. If the messages don't contain the \
answer, say so plainly.
- The chat messages may be in Chinese, Japanese, or English. The question is \
usually in English. Translate as needed and answer in the SAME language as the \
question (default English).
- When the initial context looks thin, incomplete, or off-topic for the \
question, call the search_messages tool with a focused query (you may call it \
multiple times with different phrasings, including in the likely source \
language) before answering.
- Cite who said what and roughly when where it matters (use sender names and \
timestamps from the context). Quote or paraphrase the original message.
- Be concise and factual. Surface disagreement or uncertainty in the source \
messages rather than smoothing it over."""


SEARCH_TOOL = {
    "name": "search_messages",
    "description": (
        "Semantic search over the factory-floor chat message store (LINE/WeChat "
        "group messages). Call this when the context you were given is thin, "
        "missing detail, or doesn't clearly answer the question — e.g. to find "
        "related messages, follow-ups, or messages phrased differently (try the "
        "likely source language, e.g. Chinese/Japanese, for better recall). "
        "Returns the top matching messages with sender, timestamp, and text."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "What to search for. A short phrase or keywords describing the "
                    "information you need. Can be in English, Chinese, or Japanese."
                ),
            },
            "k": {
                "type": "integer",
                "description": "How many messages to return (default 8, max 25).",
            },
        },
        "required": ["query"],
    },
}

MAX_TOOL_ITERATIONS = 5


def _format_hit(h: Hit) -> str:
    who = h.sender_name or h.sender_id or "unknown"
    ts = h.ts.isoformat(timespec="seconds") if h.ts else "?"
    return f"[#{h.id} | {ts} | {who} | {h.source}/{h.chat_id}] {h.text}"


def _format_hits(hits: list[Hit]) -> str:
    if not hits:
        return "(no messages found)"
    return "\n".join(_format_hit(h) for h in hits)


def _run_search_tool(tool_input: dict, *, source: str | None, chat_id: str | None) -> str:
    """Execute the search_messages tool. Stays within the outer source/chat scope."""
    query = (tool_input or {}).get("query", "")
    k = int((tool_input or {}).get("k", 8) or 8)
    k = max(1, min(k, 25))
    if not query:
        return "Error: empty query."
    hits = search(query, k=k, source=source, chat_id=chat_id)
    log.info("tool search_messages(%r, k=%d) -> %d hits", query, k, len(hits))
    return _format_hits(hits)


def answer_question(
    question: str,
    source: str | None = None,
    chat_id: str | None = None,
    *,
    k: int = 8,
) -> str:
    """Answer a natural-language question using retrieved messages + Claude.

    `source` / `chat_id` optionally scope both the initial retrieval and any
    tool-driven searches Claude makes (e.g. one LINE group).
    """
    client = _get_client()

    # 1. Initial retrieval
    hits = search(question, k=k, source=source, chat_id=chat_id)
    context = _format_hits(hits)
    scope_note = ""
    if source or chat_id:
        scope_note = f"\n(Scope: source={source or 'any'}, chat_id={chat_id or 'any'})"

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                f"Retrieved messages as context:{scope_note}\n\n{context}\n\n"
                f"Question: {question}"
            ),
        }
    ]

    # Stable prefix (system + tools) is cached; per-question context lives in
    # messages after the breakpoint and is not cached.
    system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]

    # 2. Tool-use loop
    response = None
    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=8192,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            system=system,
            tools=[SEARCH_TOOL],
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            break

        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for tb in tool_blocks:
            out = _run_search_tool(tb.input, source=source, chat_id=chat_id)
            tool_results.append(
                {"type": "tool_result", "tool_use_id": tb.id, "content": out}
            )
        messages.append({"role": "user", "content": tool_results})
    else:
        log.warning("Hit MAX_TOOL_ITERATIONS without a final answer")

    # 3. Extract final text
    if response is None:
        return "No response from the model."
    text = "\n".join(b.text for b in response.content if b.type == "text").strip()
    return text or "(the model returned no text answer)"


def _format_row(r: dict) -> str:
    who = r.get("sender_name") or r.get("sender_id") or "unknown"
    ts = r["ts"].isoformat(timespec="seconds") if r.get("ts") else "?"
    return f"[{ts} | {who} | {r.get('source')}/{r.get('chat_id')}] {r.get('text')}"


def answer_question_simple(
    question: str,
    source: str | None = None,
    chat_id: str | None = None,
    *,
    limit: int = 5000,
) -> str:
    """Simple 'feed everything' mode: dump ALL stored messages into the prompt.

    No retrieval, no tool — Claude sees the entire (optionally scoped) chat
    history in chronological order and answers. Best for small datasets; for
    large histories use answer_question() (RAG) instead.
    """
    client = _get_client()
    rows = all_messages(source=source, chat_id=chat_id, limit=limit)
    transcript = "\n".join(_format_row(r) for r in rows) or "(no messages stored yet)"

    system = [{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
    user = (
        f"Here is the full chat history ({len(rows)} messages, oldest first):\n\n"
        f"{transcript}\n\n"
        f"Question: {question}"
    )
    response = client.messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=8192,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "\n".join(b.text for b in response.content if b.type == "text").strip()
    return text or "(the model returned no text answer)"


class Conversation:
    """A single ongoing chat with Claude, continuously fed LINE messages.

    - Remembers the running Q&A history (one infinite thread).
    - On each .ask(), injects only the NEW messages that arrived since the last
      turn (pulled from Postgres) as context.
    - Token guard: before sending, counts tokens; if the thread would exceed
      `max_input_tokens`, that turn falls back to RAG (retrieve only the relevant
      messages + recent history) so the request stays within the context window.

    Scope it to one conversation with source/chat_id, or leave None for all.
    The LINE messages live in Postgres (durable); the Q&A history is in-memory.
    """

    def __init__(
        self,
        source: str | None = None,
        chat_id: str | None = None,
        *,
        max_input_tokens: int = 700_000,
        rag_k: int = 8,
    ):
        self.source = source
        self.chat_id = chat_id
        self.max_input_tokens = max_input_tokens
        self.rag_k = rag_k
        self.history: list[dict] = []   # prior turns: user(context+question) / assistant
        self.cursor_id = 0              # highest message id already injected
        self.client = _get_client()
        self.system = [
            {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}
        ]

    def _pull_new_messages(self) -> list[dict]:
        rows = messages_after(self.cursor_id, source=self.source, chat_id=self.chat_id)
        if rows:
            self.cursor_id = max(r["id"] for r in rows)
        return rows

    def _count_tokens(self, messages: list[dict]) -> int:
        try:
            r = self.client.messages.count_tokens(
                model=settings.ANTHROPIC_MODEL, system=self.system, messages=messages
            )
            return r.input_tokens
        except Exception:  # noqa: BLE001 - fall back to a cheap heuristic
            chars = sum(len(str(m["content"])) for m in messages)
            return chars // 4

    def ask(self, question: str) -> str:
        new_rows = self._pull_new_messages()
        delta = "\n".join(_format_row(r) for r in new_rows) or "(no new messages)"

        # Default (ongoing-chat) turn: history + new-message delta + question.
        user_turn = {
            "role": "user",
            "content": f"New chat messages since last turn:\n{delta}\n\nQuestion: {question}",
        }
        candidate = self.history + [user_turn]

        tokens = self._count_tokens(candidate)
        mode = "chat"
        if tokens > self.max_input_tokens:
            # Fall back to RAG: retrieve only relevant messages, keep recent history.
            mode = "rag"
            hits = search(question, k=self.rag_k, source=self.source, chat_id=self.chat_id)
            user_turn = {
                "role": "user",
                "content": f"Relevant chat messages:\n{_format_hits(hits)}\n\nQuestion: {question}",
            }
            candidate = self.history[-4:] + [user_turn]  # last ~2 Q&A pairs
            tokens = self._count_tokens(candidate)

        log.info("Conversation.ask mode=%s tokens=%d turns=%d", mode, tokens, len(candidate))

        response = self.client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=8192,
            thinking={"type": "adaptive"},
            output_config={"effort": "medium"},
            system=self.system,
            messages=candidate,
        )
        answer = "\n".join(b.text for b in response.content if b.type == "text").strip()
        answer = answer or "(the model returned no text answer)"

        # Persist this turn into the running thread.
        self.history = candidate + [{"role": "assistant", "content": answer}]
        return answer
