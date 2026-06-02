"""Interactive single ongoing chat with Claude, continuously fed LINE messages.

Each question you type pulls in any LINE messages that arrived since your last
turn and injects them as context, while remembering the whole conversation.

Usage:
    ../.venv/bin/python -m scripts.chat
    ../.venv/bin/python -m scripts.chat --source line --chat-id Cfactory

Type your question and press Enter. Type 'exit' or Ctrl-D to quit.
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.claude_client import Conversation  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--chat-id")
    args = ap.parse_args()

    convo = Conversation(source=args.source, chat_id=args.chat_id)
    print("Ongoing chat with Claude (fed your LINE messages). Type 'exit' to quit.\n")
    while True:
        try:
            q = input("you> ").strip()
        except EOFError:
            print()
            break
        if not q:
            continue
        if q.lower() in {"exit", "quit"}:
            break
        answer = convo.ask(q)
        print(f"\nclaude> {answer}\n")


if __name__ == "__main__":
    main()
