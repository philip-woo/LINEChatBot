"""FastAPI app: webhook ingestion endpoints (LINE now; WeChat/Slack later)."""
import logging

from fastapi import FastAPI, Request, Response, HTTPException

from .db import init_db
from .ingest import line as line_ingest

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("main")

app = FastAPI(title="Factory Assistant")


@app.on_event("startup")
def _startup():
    init_db()
    log.info("DB schema ensured.")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/webhooks/line")
async def line_webhook(request: Request):
    body = (await request.body()).decode("utf-8")
    signature = request.headers.get("X-Line-Signature", "")
    try:
        events = line_ingest.parse_events(body, signature)
    except line_ingest.InvalidSignatureError:
        log.warning("LINE: invalid signature, rejecting")
        raise HTTPException(status_code=400, detail="invalid signature")
    stored = line_ingest.handle_events(events)
    log.info("LINE webhook: %d event(s), %d stored", len(events), stored)
    return Response(content="OK", media_type="text/plain")
