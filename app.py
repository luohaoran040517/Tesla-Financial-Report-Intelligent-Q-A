from __future__ import annotations

import pandas as pd
import streamlit as st

from src.core.config import AppConfig
from src.core.qa_engine import QAEngine


@st.cache_resource
def _load_engine() -> QAEngine:
    return QAEngine(AppConfig())


def main() -> None:
    st.set_page_config(page_title="Tesla 跨年财报智能问答", layout="wide")
    st.title("Tesla 跨年财报智能问答（2021-2025）")

    with st.sidebar:
        st.header("查询设置")
        scope_label = st.selectbox("文档范围", ["all", "10-K", "10-Q"], index=0)
        years = st.multiselect(
            "年份过滤",
            [2021, 2022, 2023, 2024, 2025],
            default=[],
            help="默认不选；留空时系统将根据问题自动识别年份。",
        )
        auto_topk = st.checkbox("自动 TopK（推荐）", value=True)
        topk = st.slider("手动召回 TopK", min_value=4, max_value=20, value=8, step=1, disabled=auto_topk)
        debug = st.checkbox("显示检索调试信息", value=True)

    query = st.text_area(
        "输入复杂问题",
        value="In 2021 (Q1-Q4), which quarter has the highest Automotive gross margin? Return the quarter, value, and source page.",
        height=120,
    )

    if st.button("提交问题", type="primary"):
        with st.spinner("检索并生成答案中..."):
            engine = _load_engine()
            result = engine.answer(
                query=query,
                scope=scope_label,
                years=years,
                debug=debug,
                topk=None if auto_topk else topk,
            )

        st.subheader("答案")
        st.write(result.answer)

        st.subheader("引用证据")
        citation_rows = [c.model_dump() for c in result.citations]
        if citation_rows:
            st.dataframe(pd.DataFrame(citation_rows), width="stretch")
        else:
            st.info("无引用")

        st.subheader("计算明细")
        if result.calc_table:
            st.dataframe(pd.DataFrame(result.calc_table), width="stretch")
        else:
            st.info("无可计算表格结果")

        if debug:
            st.subheader("检索调试")
            st.json(result.debug)
            st.subheader("命中内容预览")
            preview = [
                {
                    "chunk_id": c["chunk_id"],
                    "doc_type": c["doc_type"],
                    "time_label": c["time_label"],
                    "page": c["page"],
                    "section": c["section"],
                    "content_head": c["content"][:240],
                }
                for c in result.retrieved_chunks
            ]
            st.dataframe(pd.DataFrame(preview), width="stretch")


if __name__ == "__main__":
    main()
