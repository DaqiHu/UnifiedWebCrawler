from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from crawler_app.analysis import (
    build_category_summary,
    build_focus_insights,
    build_overview_metrics,
    build_skill_matrix,
    build_skill_summary,
    build_tag_summary,
    enrich_jobs_dataframe,
    split_non_empty_lines,
)
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


def run_category_sync(service: CrawlService, source: str, category_id: str) -> None:
    with st.spinner("正在同步该类别的全部实习岗位..."):
        job_count, run_id = service.sync_category_jobs(source=source, competency_type_id=category_id, internships_only=True)
    st.success(f"已完成类别全量同步，运行 #{run_id}，新增/更新 {job_count} 个岗位。")


def run_full_sync(service: CrawlService, source: str) -> None:
    with st.spinner("正在同步 miHoYo 全站实习岗位..."):
        job_count, run_id = service.sync_all_jobs(source=source, internships_only=True)
    st.success(f"已完成全站全量同步，运行 #{run_id}，新增/更新 {job_count} 个岗位。")


service = get_service()
storage = service.storage
connectors = get_connectors()
connector = connectors[DEFAULT_SOURCE]
category_counts = service.fetch_category_counts(DEFAULT_SOURCE, internships_only=True)
category_options = {item["competencyType"]: f'{item["competencyTypeName"]} ({item["count"]})' for item in category_counts}

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
    crawl_mode = st.radio(
        "抓取模式",
        options=["单岗位 + 相似岗位", "同类别全量（仅实习）", "全站全量（仅实习）"],
    )
    target = st.text_input("岗位 URL 或岗位 ID", value=DEFAULT_TARGET)
    related_limit = st.slider("相似岗位抓取数", min_value=3, max_value=20, value=10)
    selected_category_id = st.selectbox(
        "类别（全量同步时使用）",
        options=list(category_options.keys()),
        format_func=lambda key: category_options[key],
    )
    if st.button("执行抓取 / 同步", type="primary", use_container_width=True):
        try:
            if crawl_mode == "单岗位 + 相似岗位":
                run_crawl(service, source_label, target, related_limit)
            elif crawl_mode == "同类别全量（仅实习）":
                run_category_sync(service, source_label, selected_category_id)
            else:
                run_full_sync(service, source_label)
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
st.info(
    "支持三种范围：单岗位样本抓取、同类别全量实习抓取、全站全量实习抓取。"
    " 程序 55 / 美术 27 / 产品策划 16 属于全站实习全量统计。"
)

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

overview_tab, focus_tab, jobs_tab, detail_tab, raw_tab, runs_tab = st.tabs(
    ["概览", "关注", "岗位表格", "岗位详情与对比", "原始数据", "运行记录"]
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
        category_count_text = "，".join(f"{item['competencyTypeName']} {item['count']}" for item in category_counts[:8])
        st.caption(f"米哈游当前实习类别计数：{category_count_text}")
        chart_columns = st.columns([1.2, 1])
        skill_df = build_skill_summary(jobs_df)
        chart_columns[0].plotly_chart(
            px.bar(
                skill_df.head(12),
                x="topic",
                y="count",
                title="跨领域关键词覆盖",
                text_auto=True,
            ),
            use_container_width=True,
        )
        category_df = build_category_summary(jobs_df)
        chart_columns[1].plotly_chart(
            px.bar(
                category_df,
                x="category",
                y="count",
                title="岗位类别分布",
                text_auto=True,
            ),
            use_container_width=True,
        )

        lower_columns = st.columns([1, 1])
        location_df = jobs_df.groupby("location", as_index=False)["job_id"].count().rename(columns={"job_id": "count"})
        lower_columns[0].plotly_chart(
            px.bar(
                location_df,
                x="location",
                y="count",
                title="岗位城市分布",
                text_auto=True,
            ),
            use_container_width=True,
        )
        tag_df = build_tag_summary(jobs_df)
        if not tag_df.empty:
            lower_columns[1].plotly_chart(
                px.bar(
                    tag_df.head(10),
                    x="tag",
                    y="count",
                    title="岗位标签覆盖",
                    text_auto=True,
                ),
                use_container_width=True,
            )
        else:
            lower_columns[1].info("当前样本中暂无岗位标签。")

        st.subheader("最近抓取的数据")
        display_df = jobs_df[
            [
                "job_id",
                "title",
                "location",
                "category",
                "job_nature",
                "target_audience",
                "summary_count",
                "requirement_count",
                "bonus_count",
                "delivery_count",
                "updated_at",
            ]
        ].copy()
        display_df["updated_at"] = display_df["updated_at"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

with focus_tab:
    if jobs_df.empty:
        st.info("当前数据库还没有数据。先在左侧点击“抓取 / 刷新当前数据”。")
    else:
        focus_insights = build_focus_insights(jobs_df)
        st.caption("以下结论基于岗位 JD 文本做启发式推断，适合先筛选，再回到岗位详情做人工确认。")

        with st.expander("1. 哪些岗位在做跨界融合", expanded=True):
            st.write(focus_insights["cross_domain"]["description"])
            st.caption(focus_insights["cross_domain"]["summary"])
            st.dataframe(focus_insights["cross_domain"]["table"], use_container_width=True, hide_index=True)

        with st.expander("2. 哪些岗位前期准备时间相对少，且尽量没有测试", expanded=True):
            st.write(focus_insights["low_prep"]["description"])
            st.caption(focus_insights["low_prep"]["summary"])
            st.dataframe(focus_insights["low_prep"]["table"], use_container_width=True, hide_index=True)

        with st.expander("3. 哪些岗位更容易看清公司全貌与生产管线", expanded=True):
            st.write(focus_insights["pipeline"]["description"])
            st.caption(focus_insights["pipeline"]["summary"])
            st.dataframe(focus_insights["pipeline"]["table"], use_container_width=True, hide_index=True)
            st.caption("高频岗位关系边")
            st.dataframe(focus_insights["pipeline"]["edges"], use_container_width=True, hide_index=True)

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
                "tags_text",
                "summary_count",
                "responsibility_count",
                "requirement_count",
                "bonus_count",
                "delivery_count",
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
        if selected_job["tags_text"]:
            st.caption(f"岗位标签: {selected_job['tags_text']}")

        text_cols = st.columns(2)
        with text_cols[0]:
            st.subheader("岗位摘要")
            summary_lines = split_non_empty_lines(selected_job["summary"])
            if summary_lines:
                for line in summary_lines:
                    st.write(line)
            else:
                st.write("无")

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

            st.subheader("投递说明")
            delivery_lines = split_non_empty_lines(selected_job["delivery_instructions"])
            if delivery_lines:
                for line in delivery_lines:
                    st.write(line)
            else:
                st.write("无")

            st.subheader("岗位链接")
            st.markdown(f"[{selected_job['url']}]({selected_job['url']})")

        st.subheader("相似岗位")
        related_df = storage.related_jobs_dataframe(DEFAULT_SOURCE, selected_job_id)
        st.dataframe(related_df, use_container_width=True, hide_index=True)

        st.subheader("岗位对比")
        comparison_ids = st.multiselect(
            "选择要对比的岗位，支持程序 / 策划 / 美术跨方向一起分析",
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
