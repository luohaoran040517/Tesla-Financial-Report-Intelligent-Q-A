from __future__ import annotations

import json
import re
from dataclasses import dataclass

from rapidfuzz import fuzz


@dataclass
class CalcResult:
    rows: list[dict]
    summary: str


def _to_number(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    s = s.replace(",", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if s.endswith("%"):
        s = s[:-1]
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if neg else val


def _normalize_key(key: str) -> str:
    return re.sub(r"\s+", " ", key.lower().strip())


def _pick_metric_key(sample: dict, question: str) -> str | None:
    q = question.lower()
    candidates = list(sample.keys())
    best_key = None
    best_score = 0
    for key in candidates:
        score = fuzz.partial_ratio(_normalize_key(key), q)
        if score > best_score:
            best_score = score
            best_key = key
    if best_score < 45:
        return None
    return best_key


def compute_from_tables(question: str, retrieved_chunks: list[dict]) -> CalcResult:
    table_rows: list[dict] = []
    for chunk in retrieved_chunks:
        if chunk.get("chunk_type") != "table":
            continue
        raw = chunk.get("table_json_records")
        if not raw:
            continue
        try:
            rows = json.loads(raw)
            if isinstance(rows, list):
                for row in rows:
                    row["_source_chunk_id"] = chunk["chunk_id"]
                    row["_time_label"] = chunk["time_label"]
                    table_rows.append(row)
        except Exception:
            continue

    if not table_rows:
        return CalcResult(rows=[], summary="未在检索结果中找到可计算表格数据。")

    key = _pick_metric_key(table_rows[0], question)
    if not key:
        return CalcResult(rows=[], summary="找到了表格，但未定位到稳定的指标列。")

    numeric_rows: list[dict] = []
    for row in table_rows:
        val = _to_number(row.get(key))
        if val is None:
            continue
        numeric_rows.append(
            {
                "time_label": row.get("_time_label", "unknown"),
                "source_chunk_id": row.get("_source_chunk_id", ""),
                "metric_key": key,
                "value": val,
            }
        )

    if not numeric_rows:
        return CalcResult(rows=[], summary=f"定位到指标列 `{key}`，但无法解析为数值。")

    q = question.lower()
    if any(x in q for x in ["总和", "sum", "合计"]):
        total = sum(r["value"] for r in numeric_rows)
        return CalcResult(rows=numeric_rows, summary=f"指标 `{key}` 计算总和为 {total:.4f}。")

    if any(x in q for x in ["最高", "最大", "max"]):
        best = max(numeric_rows, key=lambda x: x["value"])
        return CalcResult(rows=numeric_rows, summary=f"指标 `{key}` 最大值为 {best['value']:.4f}，季度 {best['time_label']}。")

    if any(x in q for x in ["最低", "最小", "min"]):
        worst = min(numeric_rows, key=lambda x: x["value"])
        return CalcResult(rows=numeric_rows, summary=f"指标 `{key}` 最小值为 {worst['value']:.4f}，季度 {worst['time_label']}。")

    if any(x in q for x in ["环比", "qoq"]):
        by_time = sorted(numeric_rows, key=lambda x: x["time_label"])
        if len(by_time) >= 2:
            last, prev = by_time[-1], by_time[-2]
            delta = last["value"] - prev["value"]
            pct = 0.0 if prev["value"] == 0 else delta / prev["value"] * 100
            return CalcResult(
                rows=by_time,
                summary=(
                    f"指标 `{key}` 最近一期环比变化：{prev['time_label']} -> {last['time_label']}，"
                    f"变化 {delta:.4f}（{pct:.2f}%）。"
                ),
            )

    return CalcResult(rows=numeric_rows, summary=f"已提取指标 `{key}` 的 {len(numeric_rows)} 条数值，可用于进一步推理。")

