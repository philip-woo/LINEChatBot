"""CLI to ask the Claude-powered assistant a question over stored messages.

Usage:
    ../.venv/bin/python -m scripts.ask "what did the team say about the connector defect?"
    ../.venv/bin/python -m scripts.ask "any issues on line 3?" --source line --chat-id Cfactory
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.claude_client import answer_question, answer_question_simple  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--source")
    ap.add_argument("--chat-id")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--all", action="store_true",
                    help="Feed ALL stored messages to Claude instead of RAG retrieval")
    args = ap.parse_args()

    print(f"\nQ: {args.question}\n")
    if args.all:
        answer = answer_question_simple(args.question, source=args.source, chat_id=args.chat_id)
    else:
        answer = answer_question(args.question, source=args.source, chat_id=args.chat_id, k=args.k)
    print(f"A: {answer}\n")


if __name__ == "__main__":
    main()
