from __future__ import annotations

import json
from pathlib import Path

from src.core.config import AppConfig
from src.core.qa_engine import QAEngine


UNCERTAINTY_MARKERS = [
    "证据不足",
    "无法确定",
    "无法计算",
    "无法判断",
    "不足",
    "insufficient",
    "cannot determine",
    "cannot calculate",
    "unable to",
    "not enough evidence",
    # Common mojibake patterns observed on Windows console output
    "鏃犳硶",
    "涓嶈冻",
    "璇佹嵁",
    "缂哄け",
]


def _is_uncertain_answer(answer: str) -> bool:
    text = answer.lower()
    return any(marker in text for marker in UNCERTAINTY_MARKERS)


def _score_answer(answer: str, citations: list, expected_keywords: list[str]) -> str:
    """Strict binary scoring.

    success:
      1) citations non-empty
      2) answer contains all expected_keywords
      3) answer is not uncertainty/evidence-insufficient style
    fail:
      otherwise
    """
    if not answer or not answer.strip():
        return "fail"

    if not citations:
        return "fail"

    if _is_uncertain_answer(answer):
        return "fail"

    answer_lower = answer.lower()
    if any(k.lower() not in answer_lower for k in expected_keywords):
        return "fail"

    return "success"


def _to_markdown_table(rows: list[dict]) -> str:
    header = "| ID | Question | Quality |\n|---|---|---|"
    body = "\n".join([f"| {r['id']} | {r['question']} | {r['quality']} |" for r in rows])
    return header + "\n" + body


def main() -> None:
    config = AppConfig()
    if not config.eval_questions.exists():
        raise FileNotFoundError(f"Missing eval questions file: {config.eval_questions}")

    questions = json.loads(config.eval_questions.read_text(encoding="utf-8-sig"))
    engine = QAEngine(config)

    results: list[dict] = []
    for q in questions:
        result = engine.answer(
            query=q["question"],
            scope=q.get("scope", "all"),
            years=q.get("years"),
            debug=True,
        )
        quality = _score_answer(result.answer, result.citations, q.get("expected_keywords", []))
        results.append(
            {
                "id": q["id"],
                "question": q["question"],
                "quality": quality,
                "answer": result.answer,
                "citations": [c.model_dump() for c in result.citations],
                "debug": result.debug,
            }
        )
        print(f"[eval] {q['id']}: {quality}")

    config.eval_results.parent.mkdir(parents=True, exist_ok=True)
    config.eval_results.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    success = sum(1 for r in results if r["quality"] == "success")
    fail = sum(1 for r in results if r["quality"] == "fail")

    md = [
        "# Evaluation Summary",
        "",
        "- Quality rule: strict binary (`success` / `fail`).",
        "- success requires: citations non-empty + all expected_keywords matched + no uncertainty wording.",
        "",
        f"- Total questions: {len(results)}",
        f"- Success: {success}",
        f"- Fail: {fail}",
        "",
        "## Details",
        "",
        _to_markdown_table(results),
    ]

    report_path = Path("reports/eval_summary.md")
    report_path.write_text("\n".join(md), encoding="utf-8")
    print(f"[eval] results written to: {config.eval_results}")
    print(f"[eval] summary written to: {report_path}")


if __name__ == "__main__":
    main()
