"""CLI to test semantic retrieval against stored messages.

Usage:
    ../.venv/bin/python -m scripts.query "connector defect" --k 5
    ../.venv/bin/python -m scripts.query "不良" --source line
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.retrieval import search  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--source")
    ap.add_argument("--chat-id")
    args = ap.parse_args()

    hits = search(args.query, k=args.k, source=args.source, chat_id=args.chat_id)
    if not hits:
        print("(no results)")
        return
    print(f"Top {len(hits)} for {args.query!r}:\n")
    for h in hits:
        who = h.sender_name or h.sender_id or "?"
        print(f"  [{h.score:.3f}] #{h.id} {who} ({h.source}): {h.text}")
    print()


if __name__ == "__main__":
    main()
