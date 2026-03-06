from __future__ import annotations

import pickle
from pathlib import Path

import chromadb
from rank_bm25 import BM25Okapi

from .config import AppConfig
from .embeddings import create_embedder
from .utils import flatten_for_chroma, read_jsonl, tokenize


class IndexBuilder:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.embedder = create_embedder(config.embedding_model)

    def build(self) -> dict[str, int | str]:
        chunks = read_jsonl(self.config.chunks_file)
        if not chunks:
            raise RuntimeError(f"No parsed chunks found at {self.config.chunks_file}")

        self._build_bm25(chunks)
        self._build_dense(chunks)
        return {"chunks": len(chunks), "embedding_backend": self.embedder.backend, "embedding_model": self.embedder.model_name}

    def _build_bm25(self, chunks: list[dict]) -> None:
        tokenized_corpus = [tokenize(chunk["content"]) for chunk in chunks]
        bm25 = BM25Okapi(tokenized_corpus)
        payload = {
            "bm25": bm25,
            "ids": [chunk["chunk_id"] for chunk in chunks],
            "tokenized_corpus": tokenized_corpus,
        }
        self.config.bm25_file.parent.mkdir(parents=True, exist_ok=True)
        with self.config.bm25_file.open("wb") as f:
            pickle.dump(payload, f)

    def _build_dense(self, chunks: list[dict]) -> None:
        client = chromadb.PersistentClient(path=str(self.config.chroma_dir))
        try:
            client.delete_collection(self.config.chroma_collection)
        except Exception:
            pass

        collection = client.create_collection(name=self.config.chroma_collection)

        texts = [chunk["content"] for chunk in chunks]
        embeddings = self.embedder.encode(texts, normalize_embeddings=True, show_progress_bar=True).tolist()
        metadatas = [
            flatten_for_chroma(
                {
                    "chunk_id": chunk["chunk_id"],
                    "doc_type": chunk["doc_type"],
                    "year": chunk["year"],
                    "quarter": chunk["quarter"],
                    "time_label": chunk["time_label"],
                    "file_name": chunk["file_name"],
                    "page": chunk["page"],
                    "section": chunk["section"],
                    "chunk_type": chunk["chunk_type"],
                    "terms": chunk.get("terms", []),
                }
            )
            for chunk in chunks
        ]

        collection.add(
            ids=[chunk["chunk_id"] for chunk in chunks],
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings,
        )


def load_bm25(path: Path) -> dict:
    with path.open("rb") as f:
        return pickle.load(f)
