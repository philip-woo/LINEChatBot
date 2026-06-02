"""Local multilingual embeddings via fastembed (ONNX, no PyTorch, no API key).

Default model: paraphrase-multilingual-MiniLM-L12-v2 (384-dim), good for zh/ja/en.

Swappable: set EMBED_MODEL / EMBED_DIM in .env (and the vector(N) in schema.sql).
"""
import warnings
from functools import lru_cache

from fastembed import TextEmbedding

from .config import settings

# fastembed notes a pooling change for this model; harmless since we embed
# queries and passages identically. Silence to keep CLI/logs clean.
warnings.filterwarnings("ignore", message=".*mean pooling.*")


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    return TextEmbedding(model_name=settings.EMBED_MODEL)


def embed_passage(text: str) -> list[float]:
    """Embed a stored message for indexing."""
    return next(_model().embed([text])).tolist()


def embed_query(text: str) -> list[float]:
    """Embed a search query for retrieval (same space as passages)."""
    return next(_model().embed([text])).tolist()
