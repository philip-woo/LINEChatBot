"""Print recent stored messages from Postgres.

Usage: ../.venv/bin/python -m scripts.read [--limit N]
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import recent_messages  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=50)
    args = ap.parse_args()

    rows = recent_messages(args.limit)
    if not rows:
        print("(no messages stored yet)")
        return
    print(f"{len(rows)} message(s), newest first:\n")
    for r in rows:
        who = r["sender_name"] or (r["sender_id"] or "?")
        where = f" in {r['chat_id']}" if r["chat_id"] else ""
        print(f"  #{r['id']:<4} [{r['ts']}] {who}{where} ({r['source']})")
        print(f"        {r['text']}")
    print()


if __name__ == "__main__":
    main()
