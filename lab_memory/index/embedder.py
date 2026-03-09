"""Text embedding using sentence-transformers."""
from __future__ import annotations

import os
import ssl

import numpy as np
from sentence_transformers import SentenceTransformer

_model: SentenceTransformer | None = None


def _disable_ssl_verify():
    """Disable SSL verification for model download behind corporate proxies."""
    os.environ["HF_HUB_DISABLE_SSL_VERIFY"] = "1"
    os.environ["CURL_CA_BUNDLE"] = ""
    # Monkey-patch requests to skip SSL verification
    import requests
    _orig_request = requests.Session.request

    def _patched_request(self, *args, **kwargs):
        kwargs.setdefault("verify", False)
        return _orig_request(self, *args, **kwargs)

    requests.Session.request = _patched_request
    # Suppress InsecureRequestWarning
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_model(model_name: str = "intfloat/multilingual-e5-large") -> SentenceTransformer:
    """Load or return cached embedding model."""
    global _model
    if _model is None:
        _disable_ssl_verify()
        _model = SentenceTransformer(model_name)
    return _model


def embed_texts(
    texts: list[str],
    model_name: str = "intfloat/multilingual-e5-large",
    batch_size: int = 64,
    prefix: str = "passage: ",
) -> np.ndarray:
    """Embed a list of texts using the specified model.

    For E5 models, passages should be prefixed with 'passage: '
    and queries with 'query: '.
    """
    model = get_model(model_name)
    # E5 models require prefix
    prefixed = [f"{prefix}{t}" for t in texts]
    embeddings = model.encode(
        prefixed,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    return embeddings


def embed_query(
    query: str,
    model_name: str = "intfloat/multilingual-e5-large",
) -> np.ndarray:
    """Embed a single query text."""
    model = get_model(model_name)
    embedding = model.encode(
        [f"query: {query}"],
        normalize_embeddings=True,
    )
    return embedding[0]
