from __future__ import annotations

from io import BytesIO

import pandas as pd
import plotly.express as px
import streamlit as st

from crawler_app.analysis import build_overview_metrics, build_skill_matrix, build_skill_summary, enrich_jobs_dataframe, split_non_empty_lines
from crawler_app.config import APP_TITLE, DEFAULT_SOURCE, DEFAULT_TARGET
from crawler_app.connectors import get_connectors
from crawler_app.connectors.base import ConnectorError
from crawler_app.service import CrawlService
from crawler_app.storage import SQLiteStorage


st.set_page_config(
    page_title=APP_TITLE,
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(15, 76, 117, 0.12), transparent 24rem),
                linear-gradient(180deg, #f8fbff 0%, #eef3f9 100%);
        }
        .source-card {
            border: 1px solid rgba(15, 76, 117, 0.15);
            border-radius: 16px;
            padding: 1rem 1.2rem;
            background: rgba(255, 255, 255, 0.92);
            box-shadow: 0 8px 30px rgba(15, 76, 117, 0.08);
            min-height: 126px;
        }
        .source-card h4 {
            margin: 0 0 0.4rem 0;
        }
        .mono {
            font-family: Consolas, monospace;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_service() -> CrawlService:
    return CrawlService(SQLiteStorage())


def dataframe_to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    return dataframe.to_csv(index=False).encode("utf-8-sig")


def run_crawl(service: CrawlService, source: str, target: str, related_limit: int) -> None:
    with st.spinner("正在抓取并写入数据库..."):
        bundle, run_id = service.crawl_source(source=source, target=target, related_limit=related_limit)
    st.success(
        f"已完成抓取，运行 #{run_id}。主岗位: {bundle.primary_job.title}，相似岗位: {len(bundle.related_jobs)} 个。"
    )


service = get_service()
storage = service.storage
connectors = get_connectors()
connector = connectors[DEFAULT_SOURCE]

jobs_df = storage.jobs_dataframe(DEFAULT_SOURCE)
if jobs_df.empty and "auto_bootstrapped" not in st.session_state:
    st.session_state["auto_bootstrapped"] = True
    try:
        run_crawl(service, DEFAULT_SOURCE, DEFAULT_TARGET, 10)
    except ConnectorError as error:
        st.error(f"默认样例抓取失败: {error}")
    jobs_df = storage.jobs_dataframe(DEFAULT_SOURCE)

jobs_df = enrich_jobs_dataframe(jobs_df)
runs_df = storage.crawl_runs_dataframe(DEFAULT_SOURCE, limit=20)

with st.sidebar:
    st.title("Unified Web Crawler")
    st.caption("一个 Streamlit 入口，挂接多个站点专属连接器。")
    source_label = st.selectbox(
        "数据源",
        options=[DEFAULT_SOURCE],
        format_func=lambda key: connectors[key].display_name,
    )
    target = st.text_input("岗位 URL 或岗位 ID", value=DEFAULT_TARGET)
    related_limit = st.slider("相似岗位抓取数", min_value=3, max_value=20, value=10)
    if st.button("抓取 / 刷新当前数据", type="primary", use_container_width=True):
        try:
            run_crawl(service, source_label, target, related_limit)
        except ConnectorError as error:
            st.error(str(error))
        jobs_df = enrich_jobs_dataframe(storage.jobs_dataframe(DEFAULT_SOURCE))
        runs_df = storage.crawl_runs_dataframe(DEFAULT_SOURCE, limit=20)

    st.download_button(
        "下载岗位 CSV",
        data=dataframe_to_csv_bytes(jobs_df.drop(columns=["raw_payload_json"]) if not jobs_df.empty else jobs_df),
        file_name="mihoyo_jobs.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.title("Unified Web Crawler Workbench")
st.caption("当前已接入 miHoYo 校园招聘连接器。后续新增企业招聘页或文档页面时，只需要新增连接器模块。")

catalog_columns = st.columns(3)
catalog_columns[0].markdown(
    f"""
    <div class="source-card">
        <h4>{connector.display_name}</h4>
        <div>类型: {connector.data_kind}</div>
        <div>状态: 已接入</div>
        <div style="margin-top: 0.6rem;">{connector.description}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
catalog_columns[1].markdown(
    """
    <div class="source-card">
        <h4>更多企业招聘页</h4>
        <div>类型: 招聘岗位</div>
        <div>状态: 待新增连接器</div>
        <div style="margin-top: 0.6rem;">保留同样的存储和分析工作台，仅替换抓取适配器。</div>
    </div>
    """,
    unsafe_allow_html=True,
)
catalog_columns[2].markdown(
    """
    <div class="source-card">
        <h4>文档 / 文章页面</h4>
        <div>类型: 文档抓取</div>
        <div>状态: 待新增连接器</div>
        <div style="margin-top: 0.6rem;">适合接入技术文档、公告、博客，统一在工作台查看和导出。</div>
    </div>
    """,
    unsafe_allow_html=True,
)

overview_tab, jobs_tab, detail_tab, raw_tab, runs_tab = st.tabs(
    ["概览", "岗位表格", "岗位详情与对比", "原始数据", "运行记录"]
)

with overview_tab:
    metrics = build_overview_metrics(jobs_df)
    metric_columns = st.columns(4)
    metric_columns[0].metric("岗位数", metrics["jobs"])
    metric_columns[1].metric("城市数", metrics["locations"])
    metric_columns[2].metric("类别数", metrics["categories"])
    metric_columns[3].metric("实习岗位数", metrics["internships"])

    if jobs_df.empty:
        st.info("当前数据库还没有数据。先在左侧点击“抓取 / 刷新当前数据”。")
    else:
        chart_columns = st.columns([1.2, 1])
        skill_df = build_skill_summary(jobs_df)
        chart_columns[0].plotly_chart(
            px.bar(
                skill_df.head(12),
                x="skill",
                y="count",
                title="技能与关键词覆盖",
                text_auto=True,
            ),
            use_container_width=True,
        )
        location_df = jobs_df.groupby("location", as_index=False)["job_id"].count().rename(columns={"job_id": "count"})
        chart_columns[1].plotly_chart(
            px.bar(
                location_df,
                x="location",
                y="count",
                title="岗位城市分布",
                text_auto=True,
            ),
            use_container_width=True,
        )

        st.subheader("最近抓取的数据")
        display_df = jobs_df[
            [
                "job_id",
                "title",
                "location",
                "category",
                "job_nature",
                "target_audience",
                "requirement_count",
                "bonus_count",
                "updated_at",
            ]
        ].copy()
        display_df["updated_at"] = display_df["updated_at"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

with jobs_tab:
    if jobs_df.empty:
        st.info("暂无岗位数据。")
    else:
        table_df = jobs_df[
            [
                "job_id",
                "title",
                "location",
                "category",
                "target_audience",
                "job_nature",
                "project_name",
                "responsibility_count",
                "requirement_count",
                "bonus_count",
                "url",
            ]
        ]
        st.dataframe(table_df, use_container_width=True, hide_index=True)

with detail_tab:
    if jobs_df.empty:
        st.info("暂无岗位详情数据。")
    else:
        selected_job_id = st.selectbox(
            "查看岗位详情",
            options=jobs_df["job_id"].tolist(),
            format_func=lambda job_id: f"{job_id} - {jobs_df.loc[jobs_df['job_id'] == job_id, 'title'].iloc[0]}",
        )
        selected_job = jobs_df[jobs_df["job_id"] == selected_job_id].iloc[0]
        info_cols = st.columns(4)
        info_cols[0].metric("岗位", selected_job["title"])
        info_cols[1].metric("城市", selected_job["location"])
        info_cols[2].metric("类别", selected_job["category"])
        info_cols[3].metric("面向对象", selected_job["target_audience"])

        text_cols = st.columns(2)
        with text_cols[0]:
            st.subheader("工作职责")
            for line in split_non_empty_lines(selected_job["description"]):
                st.write(line)

            st.subheader("加分项")
            bonus_lines = split_non_empty_lines(selected_job["bonus_points"])
            if bonus_lines:
                for line in bonus_lines:
                    st.write(line)
            else:
                st.write("无")

        with text_cols[1]:
            st.subheader("任职要求")
            for line in split_non_empty_lines(selected_job["requirements"]):
                st.write(line)

            st.subheader("岗位链接")
            st.markdown(f"[{selected_job['url']}]({selected_job['url']})")

        st.subheader("相似岗位")
        related_df = storage.related_jobs_dataframe(DEFAULT_SOURCE, selected_job_id)
        st.dataframe(related_df, use_container_width=True, hide_index=True)

        st.subheader("岗位对比")
        comparison_ids = st.multiselect(
            "选择要对比的岗位",
            options=jobs_df["job_id"].tolist(),
            default=[selected_job_id],
            format_func=lambda job_id: f"{job_id} - {jobs_df.loc[jobs_df['job_id'] == job_id, 'title'].iloc[0]}",
        )
        comparison_df = build_skill_matrix(jobs_df, comparison_ids)
        st.dataframe(comparison_df, use_container_width=True, hide_index=True)

with raw_tab:
    if jobs_df.empty:
        st.info("暂无原始数据。")
    else:
        raw_job_id = st.selectbox(
            "查看原始 JSON",
            options=jobs_df["job_id"].tolist(),
            key="raw_job_id",
            format_func=lambda job_id: f"{job_id} - {jobs_df.loc[jobs_df['job_id'] == job_id, 'title'].iloc[0]}",
        )
        raw_record = jobs_df[jobs_df["job_id"] == raw_job_id].iloc[0]
        st.json(raw_record["raw_payload_json"])

with runs_tab:
    if runs_df.empty:
        st.info("暂无运行记录。")
    else:
        st.dataframe(runs_df, use_container_width=True, hide_index=True)
