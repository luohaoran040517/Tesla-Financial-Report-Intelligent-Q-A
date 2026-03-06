from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import requests
from sklearn.feature_extraction.text import HashingVectorizer


class SentenceTransformerEmbedder:
    backend = "sentence-transformers"

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str], normalize_embeddings: bool = True, show_progress_bar: bool = False):
        return self._model.encode(
            texts,
            normalize_embeddings=normalize_embeddings,
            show_progress_bar=show_progress_bar,
        )


class HashingEmbedder:
    backend = "hashing"

    def __init__(self, n_features: int = 768):
        self.model_name = f"hashing-{n_features}"
        self._vectorizer = HashingVectorizer(
            n_features=n_features,
            alternate_sign=False,
            norm=None,
            ngram_range=(1, 2),
            lowercase=True,
        )

    def encode(self, texts: list[str], normalize_embeddings: bool = True, show_progress_bar: bool = False):
        mat = self._vectorizer.transform(texts).astype(np.float32)
        arr = mat.toarray()
        if normalize_embeddings:
            norms = np.linalg.norm(arr, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            arr = arr / norms
        return arr


def _network_ready_for_hf(timeout: float = 2.0) -> bool:
    try:
        requests.get("https://huggingface.co", timeout=timeout)
        return True
    except Exception:
        return False


def create_embedder(model_name: str):
    force_local = os.getenv("FORCE_LOCAL_EMBEDDING", "").strip().lower() in {"1", "true", "yes"}
    if force_local:
        return HashingEmbedder()

    # If the model path exists locally, try loading directly.
    if Path(model_name).exists():
        try:
            return SentenceTransformerEmbedder(model_name)
        except Exception:
            return HashingEmbedder()

    # For remote model IDs, avoid long retry loops when network is blocked.
    if not _network_ready_for_hf():
        return HashingEmbedder()

    try:
        return SentenceTransformerEmbedder(model_name)
    except Exception:
        return HashingEmbedder()
