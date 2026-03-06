from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pdfplumber

from .config import AppConfig
from .schema import Chunk
from .utils import chunk_text_by_tokens, detect_section, extract_terms, infer_doc_meta, tokenize, write_jsonl


class PDFParser:
    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def discover_pdfs(self) -> list[Path]:
        files: list[Path] = []
        for root in [self.config.raw_10k_dir, self.config.raw_10q_dir]:
            if root.exists():
                files.extend(sorted(root.glob("*.pdf")))
        return files

    def parse_all(self) -> list[Chunk]:
        chunks: list[Chunk] = []
        for pdf_path in self.discover_pdfs():
            chunks.extend(self.parse_file(pdf_path))
        return chunks

    def parse_file(self, pdf_path: Path) -> list[Chunk]:
        meta = infer_doc_meta(pdf_path)
        rows: list[Chunk] = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page_idx, page in enumerate(pdf.pages, start=1):
                page_text = (page.extract_text() or "").strip()
                if page_text:
                    section = detect_section(page_text)
                    for i, text_chunk in enumerate(chunk_text_by_tokens(page_text)):
                        chunk_id = f"{meta['time_label']}_{meta['doc_type']}_p{page_idx}_t{i}"
                        rows.append(
                            Chunk(
                                chunk_id=chunk_id,
                                chunk_type="text",
                                content=text_chunk,
                                tokens=len(tokenize(text_chunk)),
                                doc_type=str(meta["doc_type"]),
                                year=int(meta["year"]),
                                quarter=str(meta["quarter"]),
                                time_label=str(meta["time_label"]),
                                file_name=str(meta["file_name"]),
                                file_path=str(meta["file_path"]),
                                page=page_idx,
                                section=section,
                                terms=extract_terms(text_chunk),
                                metadata={"page_len": len(page_text)},
                            )
                        )

                tables = page.extract_tables() or []
                for table_idx, table in enumerate(tables):
                    df = pd.DataFrame(table).fillna("")
                    title = self._guess_table_title(df, page_text)
                    markdown = df.to_markdown(index=False)
                    records = df.to_dict(orient="records")
                    content = f"Table: {title}\n{markdown}"
                    chunk_id = f"{meta['time_label']}_{meta['doc_type']}_p{page_idx}_tb{table_idx}"
                    rows.append(
                        Chunk(
                            chunk_id=chunk_id,
                            chunk_type="table",
                            content=content,
                            tokens=len(tokenize(content)),
                            doc_type=str(meta["doc_type"]),
                            year=int(meta["year"]),
                            quarter=str(meta["quarter"]),
                            time_label=str(meta["time_label"]),
                            file_name=str(meta["file_name"]),
                            file_path=str(meta["file_path"]),
                            page=page_idx,
                            section=detect_section(page_text),
                            table_title=title,
                            table_json_records=json.dumps(records, ensure_ascii=False),
                            table_markdown=markdown,
                            terms=extract_terms(content),
                            metadata={"table_index": table_idx},
                        )
                    )

        return rows

    @staticmethod
    def _guess_table_title(df: pd.DataFrame, page_text: str) -> str:
        if not df.empty:
            first_row = " ".join(str(x) for x in df.iloc[0].tolist()[:3]).strip()
            if first_row:
                return first_row[:120]
        if page_text:
            lines = [line.strip() for line in page_text.splitlines() if line.strip()]
            if lines:
                return lines[0][:120]
        return "Untitled Table"


def build_parsed_chunks(config: AppConfig) -> list[dict]:
    parser = PDFParser(config)
    chunks = parser.parse_all()
    serialized = [chunk.model_dump() for chunk in chunks]
    write_jsonl(config.chunks_file, serialized)
    return serialized

