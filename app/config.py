"""Central config, loaded from environment (.env)."""
import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/factory")

    # LINE
    LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET", "")
    LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN", "")
    SKIP_LINE_SIGNATURE = os.getenv("SKIP_LINE_SIGNATURE") == "1"

    # Anthropic
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")

    # Slack
    SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
    SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "")

    # Embeddings
    EMBED_MODEL = os.getenv("EMBED_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    EMBED_DIM = int(os.getenv("EMBED_DIM", "384"))


settings = Settings()
