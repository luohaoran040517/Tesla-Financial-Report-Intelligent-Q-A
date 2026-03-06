# FAILURE_ANALYSIS (V2 Dataset Only)

- Total questions: 15
- Success: 10
- Fail: 5
- Scoring policy: strict binary (`success` / `fail`)

## Scope
This document analyzes only failed cases in the current V2 test run. Repetitive boilerplate from earlier versions was removed, and each case is expanded with four required sections:
1. Failure Symptom
2. Traceback Investigation
3. Root Cause
4. Actionable Improvement Plan

## Case V2-F1
**Question**: Provide a complete Automotive gross margin sequence for 2020 Q4, 2021 Q4, 2022 Q4, and 2023 Q4, then compute the CAGR from 2020 to 2023 with source pages.

### 1. Failure Symptom
The answer is incomplete for the requested time range. It may provide partial annual/quarterly margin context, but cannot reliably close the full 2020Q4-2023Q4 sequence required for CAGR. The final output therefore fails strict completeness requirements.

### 2. Traceback Investigation
- Retrieval returns gross-margin-related chunks, mostly from 2021-2023 filings.
- The required 2020Q4 point is not reliably available as a structured value in the current processed corpus.
- The calculator attempts downstream reasoning without a hard pre-check for full time-point coverage.

### 3. Root Cause
A coverage-gap + workflow-control issue:
- Data coverage does not fully match the requested timeline.
- The pipeline lacks a mandatory "all required points present" gate before executing CAGR computation.

### 4. Actionable Improvement Plan
- Add a **time coverage validator** before calculation (`required_points ⊆ available_points`).
- Add a **CAGR precondition rule**: if any endpoint is missing, stop and emit structured fail reason.
- Add metadata field `available_time_points` per metric to quickly reject impossible requests.

---

## Case V2-F2
**Question**: Compare Free cash flow year-over-year between 2024 Q1 and 2025 Q1, and provide three management-quoted reasons for the change with page citations.

### 1. Failure Symptom
The answer usually includes partial numerical context and/or general narrative, but does not reliably produce **three grounded management quotes** tied to the YoY change. This is a multi-constraint failure (number + quotes + citation granularity).

### 2. Traceback Investigation
- Retrieval can find 2024Q1/2025Q1 related chunks and some management discussion text.
- Evidence for "three explicit reasons" is fragmented across multiple chunks.
- The generation step is not forced to satisfy an exact quote-count schema.

### 3. Root Cause
A multi-step orchestration gap:
- No explicit decomposition into "numeric delta" + "3 quote extraction" + "merge validation".
- No final schema check enforcing minimum quote count and quote-to-page alignment.

### 4. Actionable Improvement Plan
- Introduce a staged workflow:
  1. compute YoY delta,
  2. extract reason candidates at sentence level,
  3. enforce `>=3` quoted reasons with page anchors,
  4. merge and validate.
- Add output schema validation (`reason_count`, `quote_text`, `page`) before final answer.
- Build sentence-level index for management discussion sections.

---

## Case V2-F3
**Question**: Report Cybertruck deliveries for each quarter of 2022, then calculate the full-year total with table citations.

### 1. Failure Symptom
The answer cannot provide a valid quarterly Cybertruck delivery table and full-year total with verifiable table evidence. Returned citations are often adjacent but not field-complete for the requested entity-level metric.

### 2. Traceback Investigation
- Retrieval finds general delivery/operations sections in 2022 filings.
- Parsed tables do not consistently expose a clean `Cybertruck deliveries by quarter` structure.
- Calculator cannot map extracted fields to the requested per-quarter series.

### 3. Root Cause
A schema-mismatch problem:
- Current table parsing/indexing is optimized for broad financial metrics, not product-line delivery granularity.
- Missing specialized entity mapping for vehicle model-level delivery extraction.

### 4. Actionable Improvement Plan
- Add a **vehicle-delivery parser** with canonical columns (`quarter`, `model`, `deliveries`).
- Add model alias mapping (`Cybertruck`, variant mentions).
- Add calculation guardrail: refuse aggregation unless all four quarter values are structurally present.

---

## Case V2-F4
**Question**: Compute quarterly India revenue share from 2021 to 2023, identify the peak quarter, and provide the exact percentage with sources.

### 1. Failure Symptom
The answer fails to provide a complete quarterly India share series with exact percentages. It may return regional narrative context, but not a fully computable denominator/numerator chain.

### 2. Traceback Investigation
- Retrieval returns market-risk/region-related text chunks.
- Source documents do not consistently expose quarterly India revenue as a standalone structured field.
- No reliable numerator/denominator pair is assembled for each quarter.

### 3. Root Cause
An answerability boundary issue:
- Requested metric is not directly available (or not consistently derivable) in the current structured extraction.
- The system lacks a dedicated "unanswerable-metric" detector before generation.

### 4. Actionable Improvement Plan
- Add **answerability classifier** for ratio/share questions.
- Enforce ratio prerequisites (`numerator`, `denominator`, `same_period`, `unit_consistency`).
- When prerequisites fail, return structured fail reason plus nearest available proxy metrics.

---

## Case V2-F5
**Question**: Across all 2023 10-Q filings, find the first mention of 'Dojo chip mass-production risk,' quote the sentence, cite the page, and classify the risk level as High/Medium/Low.

### 1. Failure Symptom
The answer may retrieve Dojo-adjacent text but fails to deliver the full requirement bundle: first mention ordering + exact quote + citation + explicit risk-level classification.

### 2. Traceback Investigation
- Retrieval can surface 2023 10-Q technology/risk snippets.
- "First mention" ordering is weakly handled by heuristic ranking only.
- Risk-level classification is not backed by a dedicated classifier or rule set.

### 3. Root Cause
A compound-task control issue:
- The pipeline treats this as a single generation task, but it is actually four tasks (retrieve, temporal sort, quote extract, classify).
- No cross-step consistency check ensures all four outputs are present and aligned.

### 4. Actionable Improvement Plan
- Implement explicit pipeline:
  1. candidate sentence retrieval,
  2. temporal sorting for first mention,
  3. quote lock with page citation,
  4. risk-level classification with rationale.
- Add final completeness validator requiring all fields (`first_doc`, `quote`, `page`, `risk_level`, `rationale`).

---

## Prioritized Bottlenecks Across Failures
1. Missing pre-checks for metric/time coverage before numeric computation.
2. Weak decomposition for multi-constraint questions (number + quote + ordering + classification).
3. Limited table schema specialization for entity-level metrics.
4. No formal answerability detection for unavailable derived metrics.
5. No strict output schema validation before final answer generation.

## Next Iteration Checklist
- Add coverage and answerability gates.
- Add sentence-level retrieval index for quote-heavy tasks.
- Add specialized table parsers (deliveries, ratio components).
- Add structured output validator as a hard gate before returning answer.
