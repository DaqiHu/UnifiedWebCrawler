from __future__ import annotations

import pandas as pd
import streamlit as st

from crawler_app.connectors import get_connectors
from crawler_app.connectors.base import ConnectorError
from crawler_app.pages.shared import render_back_home, render_page_header
from crawler_app.service import CrawlService
from crawler_app.storage import SQLiteStorage


SOURCE = "arc_raiders_arc"


@st.cache_resource
def get_service() -> CrawlService:
    return CrawlService(SQLiteStorage())


def dataframe_to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    return dataframe.to_csv(index=False).encode("utf-8-sig")


def table_rows_to_dataframe(rows: list[dict[str, str]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def flatten_enemy_summary(enemies_df: pd.DataFrame) -> pd.DataFrame:
    if enemies_df.empty:
        return enemies_df
    return enemies_df[
        [
            "item_id",
            "title",
            "threat_level",
            "armor",
            "primary_attack",
            "weakness",
            "health",
            "url",
            "updated_at",
        ]
    ].copy()


def run_crawl(service: CrawlService, target: str) -> None:
    with st.spinner("正在抓取 ARC Raiders 怪物页并写入数据库..."):
        bundle, run_id = service.crawl_source(source=SOURCE, target=target)
    st.success(f"已完成抓取，运行 #{run_id}。页面: {bundle.primary_enemy.title}")


def run_sync_all_enemies(service: CrawlService, only_missing: bool) -> None:
    with st.spinner("正在同步 ARC Raiders 怪物页..."):
        result = service.sync_arc_raiders_arc(source=SOURCE, only_missing=only_missing)

    st.session_state["arc_enemy_sync_result"] = result
    synced_count = len(result["synced"])
    failed_count = len(result["failures"])
    skipped_count = len(result["skipped_titles"])
    total_count = len(result["discovered_titles"])

    if failed_count:
        failed_titles = ", ".join(item["title"] for item in result["failures"])
        st.warning(
            f"批量同步完成：成功 {synced_count} 页，失败 {failed_count} 页，跳过 {skipped_count} 页，共发现 {total_count} 页。"
        )
        st.caption(f"失败页面: {failed_titles}")
        return

    st.success(
        f"批量同步完成：成功 {synced_count} 页，跳过 {skipped_count} 页，共发现 {total_count} 页。"
    )


def render_page() -> None:
    service = get_service()
    storage = service.storage
    connectors = get_connectors()
    connector = connectors[SOURCE]

    enemies_df = storage.arc_enemies_dataframe(SOURCE)
    bootstrap_key = "arc_enemy_auto_bootstrapped"
    if enemies_df.empty and bootstrap_key not in st.session_state:
        st.session_state[bootstrap_key] = True
        try:
            run_crawl(service, connector.default_target)
        except ConnectorError as error:
            st.error(f"默认样例抓取失败: {error}")
        enemies_df = storage.arc_enemies_dataframe(SOURCE)

    runs_df = storage.crawl_runs_dataframe(SOURCE, limit=20)

    with st.sidebar:
        render_back_home()
        st.title("ARC Raiders 怪物页")
        st.caption("抓取 ARC 敌人的基础属性、战斗提示、掉落和图鉴条目。")
        target = st.text_input("怪物页面 URL 或标题", value=connector.default_target)
        only_missing = st.checkbox("批量同步时仅抓取缺失页面", value=True)
        if st.button("执行抓取", type="primary", use_container_width=True):
            try:
                run_crawl(service, target)
            except ConnectorError as error:
                st.error(str(error))
            enemies_df = storage.arc_enemies_dataframe(SOURCE)
            runs_df = storage.crawl_runs_dataframe(SOURCE, limit=20)
        if st.button("同步 ARC 怪物页", use_container_width=True):
            try:
                run_sync_all_enemies(service, only_missing=only_missing)
            except ConnectorError as error:
                st.error(str(error))
            enemies_df = storage.arc_enemies_dataframe(SOURCE)
            runs_df = storage.crawl_runs_dataframe(SOURCE, limit=20)

        summary_df = flatten_enemy_summary(enemies_df)
        st.download_button(
            "下载怪物 CSV",
            data=dataframe_to_csv_bytes(summary_df if not summary_df.empty else pd.DataFrame()),
            file_name="arc_raiders_arc_enemies.csv",
            mime="text/csv",
            use_container_width=True,
        )

    render_page_header(
        "ARC Raiders 怪物资料工作台",
        "围绕 ARC 敌人建立独立数据页，方便后续做敌人机制和掉落分析。",
    )
    st.info("当前实现从 ARC 总览页的 Variants 表发现怪物标题，并用 MediaWiki parse API 解析详情页。")
    sync_result = st.session_state.get("arc_enemy_sync_result")
    if sync_result:
        st.caption(
            "最近一次批量同步: "
            f"发现 {len(sync_result['discovered_titles'])} 页，"
            f"同步 {len(sync_result['synced'])} 页，"
            f"跳过 {len(sync_result['skipped_titles'])} 页，"
            f"失败 {len(sync_result['failures'])} 页。"
        )

    overview_tab, detail_tab, raw_tab, runs_tab = st.tabs(["概览", "怪物详情", "原始数据", "运行记录"])

    with overview_tab:
        if enemies_df.empty:
            st.info("当前数据库还没有怪物页数据。")
        else:
            latest = enemies_df.iloc[0]
            metric_cols = st.columns(5)
            metric_cols[0].metric("已抓页面数", int(enemies_df["item_id"].nunique()))
            metric_cols[1].metric("最近页面", latest["title"])
            metric_cols[2].metric("威胁等级", latest["threat_level"])
            metric_cols[3].metric("护甲", latest["armor"])
            metric_cols[4].metric("主攻击", latest["primary_attack"])

            st.subheader("已抓怪物页")
            summary_df = flatten_enemy_summary(enemies_df).copy()
            summary_df["updated_at"] = pd.to_datetime(summary_df["updated_at"], utc=True, errors="coerce")
            summary_df["updated_at"] = summary_df["updated_at"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

    with detail_tab:
        if enemies_df.empty:
            st.info("暂无怪物详情数据。")
        else:
            selected_item_id = st.selectbox(
                "查看怪物详情",
                options=enemies_df["item_id"].tolist(),
                format_func=lambda item_id: f"{item_id} - {enemies_df.loc[enemies_df['item_id'] == item_id, 'title'].iloc[0]}",
            )
            enemy = enemies_df[enemies_df["item_id"] == selected_item_id].iloc[0]

            info_cols = st.columns(6)
            info_cols[0].metric("怪物", enemy["title"])
            info_cols[1].metric("威胁等级", enemy["threat_level"])
            info_cols[2].metric("护甲", enemy["armor"])
            info_cols[3].metric("主攻击", enemy["primary_attack"])
            info_cols[4].metric("弱点", enemy["weakness"])
            info_cols[5].metric("生命值", enemy["health"])

            summary_col, stats_col = st.columns([1.2, 1])
            with summary_col:
                st.subheader("概述")
                if enemy["summary"]:
                    for paragraph in enemy["summary"].split("\n\n"):
                        st.write(paragraph)
                else:
                    st.write("无")

                st.subheader("战斗提示")
                if enemy["combat_tips_json"]:
                    for item in enemy["combat_tips_json"]:
                        st.write(f"- {item}")
                else:
                    st.write("无")

                st.subheader("图鉴条目")
                st.write(enemy["codex_entry"] or "无")

            with stats_col:
                st.subheader("基础属性")
                stats_df = pd.DataFrame(
                    [{"属性": key, "值": value} for key, value in enemy["stats_json"].items()]
                )
                st.dataframe(stats_df, use_container_width=True, hide_index=True)
                st.subheader("页面链接")
                st.markdown(f"[{enemy['url']}]({enemy['url']})")

            section_tabs = st.tabs(
                ["Attack", "Behavior", "Abilities", "Loot", "Locations", "History", "Changelog"]
            )
            text_sections = {
                "Attack": enemy["attack_text"],
                "Behavior": enemy["behavior_text"],
                "Abilities": enemy["abilities_text"],
            }
            table_sections = {
                "Loot": enemy["loot_json"],
                "History": enemy["history_json"],
                "Changelog": enemy["changelog_json"],
            }
            list_sections = {
                "Locations": enemy["locations_json"],
            }
            for tab_name, tab in zip(
                ["Attack", "Behavior", "Abilities", "Loot", "Locations", "History", "Changelog"],
                section_tabs,
                strict=True,
            ):
                with tab:
                    if tab_name in text_sections:
                        st.write(text_sections[tab_name] or "无")
                    elif tab_name in list_sections:
                        values = list_sections[tab_name]
                        if values:
                            for value in values:
                                st.write(f"- {value}")
                        else:
                            st.write("无")
                    else:
                        section_df = table_rows_to_dataframe(table_sections[tab_name])
                        if section_df.empty:
                            st.write("无")
                        else:
                            st.dataframe(section_df, use_container_width=True, hide_index=True)

    with raw_tab:
        if enemies_df.empty:
            st.info("暂无原始数据。")
        else:
            raw_item_id = st.selectbox(
                "查看原始 JSON",
                options=enemies_df["item_id"].tolist(),
                key="raw_arc_enemy_id",
                format_func=lambda item_id: f"{item_id} - {enemies_df.loc[enemies_df['item_id'] == item_id, 'title'].iloc[0]}",
            )
            raw_record = enemies_df[enemies_df["item_id"] == raw_item_id].iloc[0]
            st.json(raw_record["raw_payload_json"])

    with runs_tab:
        if runs_df.empty:
            st.info("暂无运行记录。")
        else:
            st.dataframe(runs_df, use_container_width=True, hide_index=True)
