"""POST a signed fake LINE webhook event to the local service for testing.

Usage:
    ../.venv/bin/python -m scripts.send_test_line "hello"          # 1-on-1
    ../.venv/bin/python -m scripts.send_test_line "lunch?" group   # group
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.config import settings  # noqa: E402

URL = os.getenv("CALLBACK_URL", "http://127.0.0.1:8000/webhooks/line")


def main():
    text = sys.argv[1] if len(sys.argv) > 1 else "test message"
    if len(sys.argv) > 2 and sys.argv[2] == "group":
        source = {"type": "group", "groupId": "Ctestgroup0001", "userId": "Utestuser0001"}
    else:
        source = {"type": "user", "userId": "Utestuser0001"}

    payload = {
        "destination": "xxxx",
        "events": [{
            "type": "message",
            "mode": "active",
            "timestamp": int(time.time() * 1000),
            "source": source,
            "webhookEventId": "01TEST",
            "deliveryContext": {"isRedelivery": False},
            "replyToken": "0" * 32,
            "message": {
                "id": str(int(time.time() * 1000)),
                "type": "text",
                "text": text,
                "quoteToken": "qtest123",
            },
        }],
    }
    body = json.dumps(payload)
    sig = base64.b64encode(
        hmac.new(settings.LINE_CHANNEL_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    ).decode()
    r = httpx.post(URL, content=body,
                   headers={"Content-Type": "application/json", "X-Line-Signature": sig},
                   timeout=30)
    print(f"POST {URL} -> {r.status_code} {r.text!r}")


if __name__ == "__main__":
    main()
