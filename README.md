# 特斯拉跨年财报智能问答系统（2021-2025）

## 1. 项目简介
本项目实现了一个面向特斯拉 10-K/10-Q 财报的跨年智能问答系统，支持跨文档对比、数值计算、多步检索与可追溯引用。

核心能力：
- 解析文本与表格，并保留文件名/页码/章节等来源信息
- 结构化分块（章节语义分块 + 表格独立 chunk）
- 混合检索（BM25 + 向量 + RRF 融合）
- 多步问答（先证据检索，再表格计算，再答案生成）
- Streamlit 可视化交互与检索调试

## 2. 数据概览
本地已处理文档：
- `10-K`: 5 份（2021-2025）
- `10-Q`: 15 份（2021-2025，Q1/Q2/Q3）

覆盖年份：`2021, 2022, 2023, 2024, 2025`

## 3. 环境与安装（uv）
仓库已使用 `uv` 管理依赖并生成 `uv.lock`。

```powershell
$env:UV_CACHE_DIR="$PWD/.uv-cache"
uv sync
```

LLM 配置（DashScope 兼容 OpenAI）：
```powershell
$env:OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:OPENAI_API_KEY="<YOUR_API_KEY>"
$env:LLM_MODEL="qwen-plus"
```

可选：若无法下载 HuggingFace 模型，可强制本地向量降级：
```powershell
$env:FORCE_LOCAL_EMBEDDING="1"
```

## 4. 运行指南（具体代码见txt文件）
### 4.1 构建索引
```powershell
python -m src.pipeline.build_index
```

生成文件：
- `data/processed/parsed_chunks.jsonl`
- `indexes/bm25.pkl`
- `indexes/chroma/`

### 4.2 启动问答界面
```powershell
streamlit run app.py
```

### 4.3 运行高阶评测
```powershell
python -m src.pipeline.run_eval
```

生成文件：
- `eval/results.json`
- `reports/eval_summary.md`

## 5. 系统设计抉择
### 5.1 数据处理
- 文本：按页提取，保留 `doc_type/year/quarter/file/page/section`。
- 表格：保留 `table_markdown + table_json_records`，用于检索和计算双用途。

### 5.2 分块策略
- 基于章节识别（`MD&A/Liquidity/Gross Margin/Risk Factors`）进行语义分段。
- 文本按 token 窗口切分并重叠。
- 每张表格作为完整独立 chunk，避免被切碎。

### 5.3 检索与生成
- 稀疏检索：BM25（含财务术语扩展与时间归一化）。
- 稠密检索：BGE（网络不可达时自动降级 hashing embedding）。
- 融合：RRF，并支持范围过滤（`10-K/10-Q/all + years`）。
- 生成：DashScope 兼容接口；无可用配置时降级离线证据回答。

## 6. 测试集与结果摘要
测试集文件：`eval/test_questions.json`（15 个复杂问题，跨文档/跨时间/数值与文本关联，包含 10 个常规题 + 5 个 fail 压力题）。

### 6.1 评测规则
当前使用严格二分类：
- `success`：有引用（citations 非空）且答案命中该题 `expected_keywords` 的全部关键词，并且不属于“证据不足/无法判断”等不确定回答。
- `fail`：不满足上述任一条件即为 `fail`（包括空答案、无引用、关键词未全覆盖、证据不足类回答）。

### 6.2 当前结果
当前结果（详见 `reports/eval_summary.md`、`reports/eval_comparison.md`）：

| 测试集 | success | fail |
|---|---:|---:|
| V2 (15 questions) | 10 | 5 |

### 6.3 fail 压力题结果
新增 5 道 fail 压力题（`V2-F1` ~ `V2-F5`）在当前规则下均判定为 `fail`。

## 7. 失败案例深度剖析
本轮存在 5 个 `fail` 案例，详见 [FAILURE_ANALYSIS.md](FAILURE_ANALYSIS.md)。
## 8. 代码结构
```text
app.py
src/
  core/
    config.py
    parser.py
    embeddings.py
    indexer.py
    retriever.py
    calculator.py
    generator.py
    qa_engine.py
  pipeline/
    build_index.py
    run_eval.py
eval/
  test_questions.json
  results.json
reports/
  eval_summary.md
FAILURE_ANALYSIS.md
```

## 9. 已知限制
- 跨页复杂表格仍可能抽取不完整，后续建议补跨页拼接与字段标准化。
- 数值执行器目前为规则+模糊匹配，后续可引入财务指标标准词典增强精度。
- 当 HuggingFace 模型下载受限时，会自动使用本地 hashing embedding，召回质量低于 BGE。

## 10. Local BGE Model Path
If you manually downloaded a BGE model folder, point the system to that folder:

```powershell
$env:EMBEDDING_MODEL="D:\models\bge-base-en-v1.5"
python -m src.pipeline.build_index --skip-parse
```

If this path is valid and model files exist (`config.json`, tokenizer files, model weights), the system will use BGE instead of hashing fallback.




