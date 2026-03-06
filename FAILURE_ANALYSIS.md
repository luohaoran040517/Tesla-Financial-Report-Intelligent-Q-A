# FAILURE_ANALYSIS

## Current Status (After Optimizations)
- Latest eval summary: `success=10, partial=0, fail=0`.
- This file keeps the historical failure analysis from baseline and early iterations, used to explain the optimization path and why each fix was introduced.
- Stage-by-stage metrics are in `reports/eval_comparison.md`.

## Historical Failure Cases (Baseline/Early Iterations)

### Case 1: 表格被错误识别为多张碎片表
- 失败表象: 对“2022四季度研发费用总和”问题只返回了两季度数据，计算结果偏低。
- 溯源排查: 检索日志显示命中 chunk 多为同页多个 table，且字段名不一致（`Research and development`, `R&D`, 空列名）。
- 根本原因: PDF 中跨页表格被 `pdfplumber` 切断，当前解析器没有做跨页表拼接。
- 具体改进方案: 增加“同章节+同表头相似度>0.85”跨页拼接器，并在 chunk metadata 中加入 `table_group_id`。

### Case 2: 文本证据命中但同季度数值表未命中
- 失败表象: “供应链挑战+营收环比”问题只回答了供应链描述，未给出环比。
- 溯源排查: BM25 命中了 MD&A 文本；dense 召回没有把该季度收入表带入 TopK。
- 根本原因: 当前混合检索没有“季度绑定检索”机制，文本与表格仅靠语义相似度偶然关联。
- 具体改进方案: 多步检索新增 Step-B2：若先命中文本 chunk，按 `time_label` 强制二次召回同季度 table chunk。

### Case 3: 指标列选择错误
- 失败表象: “汽车毛利率最高季度”被错误映射到“Automotive revenues”。
- 溯源排查: 计算器基于 fuzzy key 选列，问题词与多个财务列相似度接近。
- 根本原因: 缺少财务指标词典到标准字段的硬映射与别名优先级。
- 具体改进方案: 建立 `metric_alias -> canonical_metric` 配置，先规则映射后再 fuzzy fallback。

### Case 4: 时间顺序推理不稳定
- 失败表象: “2021-2023自由现金流季度波动”中季度顺序错乱。
- 溯源排查: 计算器按字符串排序 `2021Q4, 2021Q3, ...` 在部分异常 label 下顺序错误。
- 根本原因: `time_label` 只做字符串处理，没有统一转时间索引。
- 具体改进方案: 存储 `year`、`quarter_index` 两个强类型字段，并以 `(year, quarter_index)` 排序。

### Case 5: 引用片段与结论不一致
- 失败表象: 生成答案提到“宏观需求走弱”，但引用页并未明确表述。
- 溯源排查: LLM 生成时融合了多个片段，引用只展示 Top3，漏掉真正支撑句。
- 根本原因: 生成阶段没有“句子级引用绑定”，仅在段落级回填 citation。
- 具体改进方案: 在生成前做“答案句子模板 + 证据句对齐”，每个结论句必须绑定至少一个 source chunk。

## 优先级改造路线（已执行）
1. 表格解析增强（跨页拼接、字段标准化）- 部分执行。
2. 多步检索的时间绑定策略（先文本后同季度表格）- 已执行。
3. 指标映射词典与数值执行器鲁棒性提升 - 已执行部分。
4. 句子级/关键词级引用约束，降低“答对但引错”风险 - 已执行部分。
5. 轻量 query planner 处理复杂复合问题 - 已执行（规则化路由）。
