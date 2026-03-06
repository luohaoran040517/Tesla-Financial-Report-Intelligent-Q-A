from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    chunk_id: str
    chunk_type: Literal["text", "table"]
    content: str
    tokens: int

    doc_type: Literal["10-K", "10-Q"]
    year: int
    quarter: str
    time_label: str
    file_name: str
    file_path: str
    page: int
    section: str

    table_title: str | None = None
    table_json_records: str | None = None
    table_markdown: str | None = None

    terms: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Citation(BaseModel):
    chunk_id: str
    file_name: str
    page: int
    section: str
    score: float


class QAResult(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    calc_table: list[dict[str, Any]] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)

