from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

TSLA_FILE_RE = re.compile(r"TSLA-Q(?P<quarter>[1-4])-(?P<year>20\d{2})", re.IGNORECASE)

SECTION_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"management['’]s discussion and analysis|md&a", re.IGNORECASE), "MD&A"),
    (re.compile(r"liquidity and capital resources|liquidity", re.IGNORECASE), "Liquidity"),
    (re.compile(r"automotive gross margin|gross margin", re.IGNORECASE), "Gross Margin"),
    (re.compile(r"risk factors|risk", re.IGNORECASE), "Risk Factors"),
]

TERM_LEXICON = {
    "free cash flow": ["free cash flow", "fcf"],
    "automotive gross margin": ["automotive gross margin", "vehicle gross margin"],
    "research and development": ["research and development", "r&d", "研发"],
    "revenue": ["revenue", "total revenues", "营收"],
    "supply chain": ["supply chain", "供应链", "parts shortage"],
    "china market": ["china", "中国市场"],
    "capacity bottleneck": ["capacity bottleneck", "产能瓶颈", "factory ramp", "bottleneck"],
}


def infer_doc_meta(path: Path) -> dict[str, str | int]:
    match = TSLA_FILE_RE.search(path.name)
    if not match:
        raise ValueError(f"Cannot parse year/quarter from filename: {path.name}")

    year = int(match.group("year"))
    q = match.group("quarter")
    return {
        "doc_type": path.parent.name,
        "year": year,
        "quarter": f"Q{q}",
        "time_label": f"{year}Q{q}",
        "file_name": path.name,
        "file_path": str(path),
    }


def detect_section(text: str, default: str = "General") -> str:
    for pattern, name in SECTION_PATTERNS:
        if pattern.search(text):
            return name
    return default


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9\-\.]+", text.lower())


def chunk_text_by_tokens(text: str, chunk_size: int = 220, overlap: int = 40) -> list[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    step = max(1, chunk_size - overlap)
    while start < len(words):
        end = min(len(words), start + chunk_size)
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += step
    return chunks


def extract_terms(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for canonical, aliases in TERM_LEXICON.items():
        if any(alias in lowered for alias in aliases):
            found.append(canonical)
    return found


def normalize_query(query: str) -> str:
    q = query
    q = re.sub(r"(20\d{2})\s*[-_/]?\s*q([1-4])", r"\1Q\2", q, flags=re.IGNORECASE)
    q = re.sub(r"q([1-4])\s*(20\d{2})", r"\2Q\1", q, flags=re.IGNORECASE)
    return q


def flatten_for_chroma(metadata: dict) -> dict:
    flat = {}
    for k, v in metadata.items():
        if isinstance(v, (str, int, float, bool)) or v is None:
            flat[k] = v
        elif isinstance(v, list):
            flat[k] = "|".join(str(x) for x in v)
        else:
            flat[k] = json.dumps(v, ensure_ascii=True)
    return flat


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
