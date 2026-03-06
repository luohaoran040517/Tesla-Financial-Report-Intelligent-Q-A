from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

import chromadb

from .config import AppConfig
from .embeddings import create_embedder
from .indexer import load_bm25
from .utils import TERM_LEXICON, normalize_query, read_jsonl, tokenize


@dataclass
class RetrievedChunk:
    chunk: dict
    bm25_score: float
    dense_rank: int
    sparse_rank: int
    fused_score: float
    rerank_score: float


class HybridRetriever:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.chunks = read_jsonl(config.chunks_file)
        self.chunk_by_id = {c["chunk_id"]: c for c in self.chunks}
        self.bm25_payload = load_bm25(config.bm25_file)
        self.embedder = create_embedder(config.embedding_model)
        client = chromadb.PersistentClient(path=str(config.chroma_dir))
        self.collection = client.get_collection(config.chroma_collection)
        self.last_query_plan: dict = {}

    def retrieve(
        self,
        query: str,
        scope: str = "all",
        years: list[int] | None = None,
        topk: int = 8,
    ) -> list[RetrievedChunk]:
        plan = self._infer_query_plan(query, topk)
        self.last_query_plan = plan

        expanded_query = self._expand_query(normalize_query(query))
        sparse = self._bm25_search(expanded_query, topk=plan["candidate_k"])
        dense = self._dense_search(expanded_query, topk=plan["candidate_k"])

        scores: dict[str, float] = defaultdict(float)
        ranks: dict[str, dict[str, int | float]] = defaultdict(dict)
        rrf_k = 60

        for rank, (chunk_id, score) in enumerate(sparse, start=1):
            scores[chunk_id] += 1.0 / (rrf_k + rank)
            ranks[chunk_id]["sparse_rank"] = rank
            ranks[chunk_id]["bm25_score"] = float(score)

        for rank, chunk_id in enumerate(dense, start=1):
            scores[chunk_id] += 1.0 / (rrf_k + rank)
            ranks[chunk_id]["dense_rank"] = rank

        candidates: list[RetrievedChunk] = []
        for chunk_id, fused in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            chunk = self.chunk_by_id.get(chunk_id)
            if not chunk:
                continue
            if not self._pass_filter(chunk, scope=scope, years=years):
                continue

            rerank = self._rerank_score(chunk, fused, plan)
            candidates.append(
                RetrievedChunk(
                    chunk=chunk,
                    bm25_score=float(ranks[chunk_id].get("bm25_score", 0.0)),
                    dense_rank=int(ranks[chunk_id].get("dense_rank", 99999)),
                    sparse_rank=int(ranks[chunk_id].get("sparse_rank", 99999)),
                    fused_score=float(fused),
                    rerank_score=float(rerank),
                )
            )

        candidates.sort(key=lambda x: x.rerank_score, reverse=True)
        deduped = self._dedup_candidates(candidates)
        selected = deduped[:topk]

        if plan["intent"] in {"hybrid", "table"}:
            selected = self._bind_time_tables(
                selected=selected,
                candidates=deduped,
                scope=scope,
                years=years,
                topk=topk,
                query_time_labels=plan["time_labels"],
            )

        return selected

    def _bm25_search(self, query: str, topk: int) -> list[tuple[str, float]]:
        tokenized = tokenize(query)
        scores = self.bm25_payload["bm25"].get_scores(tokenized)
        ids = self.bm25_payload["ids"]
        ranked = sorted(zip(ids, scores), key=lambda x: x[1], reverse=True)
        return ranked[:topk]

    def _dense_search(self, query: str, topk: int) -> list[str]:
        embedding = self.embedder.encode([query], normalize_embeddings=True)[0].tolist()
        result = self.collection.query(query_embeddings=[embedding], n_results=topk)
        return result.get("ids", [[]])[0]

    def _expand_query(self, query: str) -> str:
        q = query.lower()
        expansions: list[str] = []
        for canonical, aliases in TERM_LEXICON.items():
            if any(alias in q for alias in aliases):
                expansions.extend(aliases)
                expansions.append(canonical)
        return query + " " + " ".join(expansions)

    def _infer_query_plan(self, query: str, topk: int) -> dict:
        q = normalize_query(query).lower()
        time_labels = sorted(set(re.findall(r"20\d{2}q[1-4]", q)))

        numeric_keywords = ["sum", "total", "环比", "同比", "qoq", "yoy", "highest", "lowest", "最高", "最低", "max", "min", "calculate", "计算"]
        narrative_keywords = ["describe", "变化", "risk", "风险", "背景", "md&a", "management", "提到", "discussion", "first", "earliest"]

        is_numeric = any(k in q for k in numeric_keywords)
        is_narrative = any(k in q for k in narrative_keywords)

        if is_numeric and is_narrative:
            intent = "hybrid"
            preferred_chunk_types = ["table", "text"]
            preferred_sections = ["MD&A", "Gross Margin", "Liquidity"]
            candidate_k = max(topk * 4, 30)
        elif is_numeric:
            intent = "table"
            preferred_chunk_types = ["table", "text"]
            preferred_sections = ["Gross Margin", "Liquidity", "MD&A"]
            candidate_k = max(topk * 4, 28)
        else:
            intent = "text"
            preferred_chunk_types = ["text", "table"]
            preferred_sections = ["MD&A", "Risk Factors", "Liquidity"]
            candidate_k = max(topk * 3, 24)

        first_mention = any(k in q for k in ["first", "earliest", "首次", "最早"])

        return {
            "intent": intent,
            "preferred_chunk_types": preferred_chunk_types,
            "preferred_sections": preferred_sections,
            "time_labels": [x.upper() for x in time_labels],
            "candidate_k": candidate_k,
            "query": query,
            "first_mention": first_mention,
        }

    def _rerank_score(self, chunk: dict, fused_score: float, plan: dict) -> float:
        score = fused_score

        if chunk.get("chunk_type") == plan["preferred_chunk_types"][0]:
            score += 0.020
        elif chunk.get("chunk_type") == plan["preferred_chunk_types"][1]:
            score += 0.008

        section = chunk.get("section", "")
        if section in plan["preferred_sections"]:
            score += 0.012

        if plan["time_labels"] and chunk.get("time_label") in plan["time_labels"]:
            score += 0.030

        if plan.get("first_mention"):
            year = int(chunk.get("year", 9999))
            # Prefer earlier years for "first mention" style queries.
            score += max(0.0, (2030 - year)) * 0.001

        chunk_terms = chunk.get("terms", []) or []
        query_lower = plan["query"].lower()
        term_hits = sum(1 for t in chunk_terms if t in query_lower)
        score += min(0.015, term_hits * 0.005)

        return score

    @staticmethod
    def _dedup_candidates(candidates: list[RetrievedChunk]) -> list[RetrievedChunk]:
        out: list[RetrievedChunk] = []
        seen: set[str] = set()
        for c in candidates:
            key = f"{c.chunk.get('file_name')}|{c.chunk.get('page')}|{c.chunk.get('chunk_type')}|{c.chunk.get('section')}|{c.chunk.get('time_label')}"
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
        return out

    def _bind_time_tables(
        self,
        selected: list[RetrievedChunk],
        candidates: list[RetrievedChunk],
        scope: str,
        years: list[int] | None,
        topk: int,
        query_time_labels: list[str],
    ) -> list[RetrievedChunk]:
        selected_ids = {r.chunk["chunk_id"] for r in selected}
        selected_text_labels = {r.chunk.get("time_label") for r in selected if r.chunk.get("chunk_type") == "text"}
        target_labels = {x for x in selected_text_labels if x}
        if not target_labels and query_time_labels:
            target_labels = set(query_time_labels)

        if not target_labels:
            return selected

        table_count = sum(1 for r in selected if r.chunk.get("chunk_type") == "table")
        required_tables = min(max(1, len(target_labels)), 3)
        if table_count >= required_tables:
            return selected

        supplements: list[RetrievedChunk] = []
        for c in candidates:
            if c.chunk["chunk_id"] in selected_ids:
                continue
            if c.chunk.get("chunk_type") != "table":
                continue
            if c.chunk.get("time_label") not in target_labels:
                continue
            if not self._pass_filter(c.chunk, scope=scope, years=years):
                continue
            supplements.append(c)

        if supplements:
            selected.extend(supplements[: max(0, required_tables - table_count)])
            selected.sort(key=lambda x: x.rerank_score, reverse=True)

        return selected[:topk]

    @staticmethod
    def _pass_filter(chunk: dict, scope: str, years: list[int] | None) -> bool:
        if scope == "10-K" and chunk["doc_type"] != "10-K":
            return False
        if scope == "10-Q" and chunk["doc_type"] != "10-Q":
            return False
        if years and int(chunk["year"]) not in years:
            return False
        return True
