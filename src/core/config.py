from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    base_dir: Path = Path(__file__).resolve().parents[2]
    raw_10k_dir: Path = field(default_factory=lambda: Path("10-K"))
    raw_10q_dir: Path = field(default_factory=lambda: Path("10-Q"))
    processed_dir: Path = field(default_factory=lambda: Path("data/processed"))
    indexes_dir: Path = field(default_factory=lambda: Path("indexes"))
    chroma_dir: Path = field(default_factory=lambda: Path("indexes/chroma"))
    chunks_file: Path = field(default_factory=lambda: Path("data/processed/parsed_chunks.jsonl"))
    bm25_file: Path = field(default_factory=lambda: Path("indexes/bm25.pkl"))
    eval_questions: Path = field(default_factory=lambda: Path("eval/test_questions.json"))
    eval_results: Path = field(default_factory=lambda: Path("eval/results.json"))

    embedding_model: str = field(default_factory=lambda: os.getenv("EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5"))
    chroma_collection: str = "tesla_financial_chunks"
    default_topk: int = 8

    def ensure_dirs(self) -> None:
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.indexes_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
