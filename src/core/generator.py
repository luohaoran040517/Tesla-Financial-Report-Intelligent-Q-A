from __future__ import annotations

import os
from typing import Any


def _format_context(retrieved: list[dict], max_items: int = 10) -> str:
    lines = []
    for i, item in enumerate(retrieved[:max_items], start=1):
        lines.append(
            f"[{i}] {item['chunk_id']} | {item['doc_type']} {item['time_label']} | p{item['page']} | {item['section']}\n{item['content'][:700]}"
        )
    return "\n\n".join(lines)


def _prompt(question: str, retrieved: list[dict], calc_summary: str) -> str:
    context = _format_context(retrieved)
    return (
        "你是财报分析助手。请仅基于给定证据回答，答案使用中文。"
        "必须给出简洁结论，并在句末引用 chunk_id（如 [2023Q3_10-Q_p30_t1]）。"
        "如果证据不足要明确说不足。\n\n"
        f"问题: {question}\n"
        f"计算摘要: {calc_summary}\n"
        f"证据:\n{context}"
    )


def generate_answer(question: str, retrieved: list[dict], calc_summary: str) -> str:
    prompt = _prompt(question, retrieved, calc_summary)
    last_error: str | None = None

    # Preferred: OpenAI-compatible endpoint (works with DashScope compatible mode)
    api_key = os.getenv("OPENAI_API_KEY", "").strip() or os.getenv("DASHSCOPE_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "").strip() or os.getenv("DASHSCOPE_BASE_URL", "").strip()
    model = os.getenv("LLM_MODEL", "qwen-plus")

    if api_key and base_url:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=base_url)
            resp = client.chat.completions.create(
                model=model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": "You are a financial filing QA assistant."},
                    {"role": "user", "content": prompt},
                ],
            )
            text = resp.choices[0].message.content if resp.choices else ""
            if text:
                return text.strip()
        except Exception as e:
            last_error = f"openai-compatible call failed: {e}"

    # Secondary: native dashscope sdk
    ds_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if ds_key:
        try:
            import dashscope
            from dashscope import Generation

            dashscope.api_key = ds_key
            resp: Any = Generation.call(model="qwen-turbo", prompt=prompt, temperature=0.1)
            text = getattr(resp, "output", {}).get("text") if hasattr(resp, "output") else None
            if text:
                return text.strip()
        except Exception as e:
            last_error = f"dashscope sdk call failed: {e}"

    return _fallback_answer(question, retrieved, calc_summary, last_error)


def _fallback_answer(question: str, retrieved: list[dict], calc_summary: str, error: str | None = None) -> str:
    snippets = []
    for item in retrieved[:3]:
        snippets.append(f"[{item['chunk_id']}] {item['content'][:180].replace(chr(10), ' ')}")
    evidence = "\n".join(snippets) if snippets else "无命中证据"
    return (
        f"问题：{question}\n"
        f"计算结论：{calc_summary}\n"
        f"证据摘要：\n{evidence}\n"
        + (
            "说明：当前未检测到可用 LLM 配置，以上为离线证据拼接回答。"
            if not error
            else f"说明：LLM 调用失败（{error}），以上为离线证据拼接回答。"
        )
    )
