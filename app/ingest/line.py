"""LINE ingestion: verify signature, parse events, normalize, persist.

Mirrors the proven line-ingest prototype but writes into Postgres via the
normalized schema. Uses the v3 SDK throughout (the SDK's flask-echo example
mixes v2 parser with v3 classes, which silently drops messages).
"""
import logging
from datetime import datetime, timezone

from linebot.v3 import WebhookParser
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi

from ..config import settings
from ..models import NormalizedMessage, save_message

log = logging.getLogger("ingest.line")

# Parser verifies the X-Line-Signature HMAC unless SKIP_LINE_SIGNATURE is set (dev only).
_parser = WebhookParser(
    settings.LINE_CHANNEL_SECRET or "unset",
    skip_signature_verification=lambda: settings.SKIP_LINE_SIGNATURE,
)
_config = (
    Configuration(access_token=settings.LINE_CHANNEL_ACCESS_TOKEN)
    if settings.LINE_CHANNEL_ACCESS_TOKEN
    else None
)


def _resolve_name(source_type, chat_id, sender_id):
    """Best-effort display-name lookup (needs access token). None on failure."""
    if not _config or not sender_id:
        return None
    try:
        with ApiClient(_config) as client:
            api = MessagingApi(client)
            if source_type == "group" and chat_id:
                return api.get_group_member_profile(chat_id, sender_id).display_name
            if source_type == "room" and chat_id:
                return api.get_room_member_profile(chat_id, sender_id).display_name
            if source_type == "user":
                return api.get_profile(sender_id).display_name
    except Exception as e:  # noqa: BLE001 - best effort
        log.warning("LINE name lookup failed: %s", e)
    return None


def parse_events(body: str, signature: str):
    """Return parsed events, verifying signature unless SKIP_LINE_SIGNATURE."""
    return _parser.parse(body, signature)  # raises InvalidSignatureError


def handle_events(events) -> int:
    """Persist text messages from events. Returns count stored."""
    stored = 0
    for event in events:
        if not isinstance(event, MessageEvent):
            continue
        if not isinstance(event.message, TextMessageContent):
            continue

        src = event.source
        source_type = getattr(src, "type", None)
        # In LINE, the conversation id is group/room id, or the user id for 1-on-1.
        chat_id = (
            getattr(src, "group_id", None)
            or getattr(src, "room_id", None)
            or getattr(src, "user_id", None)
        )
        sender_id = getattr(src, "user_id", None)
        ts_ms = getattr(event, "timestamp", None)
        ts = (
            datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            if ts_ms
            else datetime.now(timezone.utc)
        )

        msg = NormalizedMessage(
            source="line",
            chat_id=chat_id,
            sender_id=sender_id,
            sender_name=_resolve_name(source_type, chat_id, sender_id),
            timestamp=ts,
            text=event.message.text,
            source_message_id=event.message.id,
            raw={"source_type": source_type, "mode": getattr(event, "mode", None)},
        )
        new_id = save_message(msg)
        if new_id:
            stored += 1
            log.info("Stored LINE msg #%s [%s] %r", new_id, source_type, event.message.text)
    return stored


# Re-export for the route layer
__all__ = ["parse_events", "handle_events", "InvalidSignatureError"]
