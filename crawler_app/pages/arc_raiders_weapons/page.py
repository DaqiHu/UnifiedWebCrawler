from __future__ import annotations

import pandas as pd
import streamlit as st

from crawler_app.connectors import get_connectors
from crawler_app.connectors.base import ConnectorError
from crawler_app.pages.shared import render_back_home, render_page_header
from crawler_app.service import CrawlService
from crawler_app.storage import SQLiteStorage


SOURCE = "arc_raiders_weapons"


@st.cache_resource
def get_service() -> CrawlService:
    return CrawlService(SQLiteStorage())


def dataframe_to_csv_bytes(dataframe: pd.DataFrame) -> bytes:
    return dataframe.to_csv(index=False).encode("utf-8-sig")


def table_rows_to_dataframe(rows: list[dict[str, str]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows)


def flatten_weapon_summary(weapons_df: pd.DataFrame) -> pd.DataFrame:
    if weapons_df.empty:
        return weapons_df
    return weapons_df[
        [
            "item_id",
            "title",
            "item_type",
            "rarity",
            "ammo_type",
            "firing_mode",
            "arc_armor_penetration",
            "magazine_size",
            "url",
            "updated_at",
        ]
    ].copy()


def run_crawl(service: CrawlService, target: str) -> None:
    with st.spinner("正在抓取 ARC Raiders 武器页并写入数据库..."):
        bundle, run_id = service.crawl_source(source=SOURCE, target=target)
    st.success(f"已完成抓取，运行 #{run_id}。页面: {bundle.primary_weapon.title}")


def render_page() -> None:
    service = get_service()
    storage = service.storage
    connectors = get_connectors()
    connector = connectors[SOURCE]

    weapons_df = storage.weapons_dataframe(SOURCE)
    bootstrap_key = "arc_auto_bootstrapped"
    if weapons_df.empty and bootstrap_key not in st.session_state:
        st.session_state[bootstrap_key] = True
        try:
            run_crawl(service, connector.default_target)
        except ConnectorError as error:
            st.error(f"默认样例抓取失败: {error}")
        weapons_df = storage.weapons_dataframe(SOURCE)

    runs_df = storage.crawl_runs_dataframe(SOURCE, limit=20)

    with st.sidebar:
        render_back_home()
        st.title("ARC Raiders 武器页")
        st.caption("独立的武器资料抓取页面。")
        target = st.text_input("武器页面 URL 或标题", value=connector.default_target)
        if st.button("执行抓取", type="primary", use_container_width=True):
            try:
                run_crawl(service, target)
            except ConnectorError as error:
                st.error(str(error))
            weapons_df = storage.weapons_dataframe(SOURCE)
            runs_df = storage.crawl_runs_dataframe(SOURCE, limit=20)

        summary_df = flatten_weapon_summary(weapons_df)
        st.download_button(
            "下载武器 CSV",
            data=dataframe_to_csv_bytes(summary_df if not summary_df.empty else pd.DataFrame()),
            file_name="arc_raiders_weapons.csv",
            mime="text/csv",
            use_container_width=True,
        )

    render_page_header(
        "ARC Raiders 武器资料工作台",
        "先从武器页抓取入手，为后续分析资源循环和玩法设计推断打底。",
    )
    st.info("当前实现以 MediaWiki parse API 为主，抽取 infobox、来源和各类资源循环表。")

    overview_tab, detail_tab, raw_tab, runs_tab = st.tabs(["概览", "武器详情", "原始数据", "运行记录"])

    with overview_tab:
        if weapons_df.empty:
            st.info("当前数据库还没有武器页数据。")
        else:
            latest = weapons_df.iloc[0]
            metric_cols = st.columns(5)
            metric_cols[0].metric("已抓页面数", int(weapons_df["item_id"].nunique()))
            metric_cols[1].metric("最近页面", latest["title"])
            metric_cols[2].metric("武器类型", latest["item_type"])
            metric_cols[3].metric("稀有度", latest["rarity"])
            metric_cols[4].metric("弹药", latest["ammo_type"])

            st.subheader("已抓武器页")
            summary_df = flatten_weapon_summary(weapons_df).copy()
            summary_df["updated_at"] = pd.to_datetime(summary_df["updated_at"], utc=True, errors="coerce")
            summary_df["updated_at"] = summary_df["updated_at"].dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

    with detail_tab:
        if weapons_df.empty:
            st.info("暂无武器详情数据。")
        else:
            selected_item_id = st.selectbox(
                "查看武器详情",
                options=weapons_df["item_id"].tolist(),
                format_func=lambda item_id: f"{item_id} - {weapons_df.loc[weapons_df['item_id'] == item_id, 'title'].iloc[0]}",
            )
            weapon = weapons_df[weapons_df["item_id"] == selected_item_id].iloc[0]

            info_cols = st.columns(5)
            info_cols[0].metric("武器", weapon["title"])
            info_cols[1].metric("类型", weapon["item_type"])
            info_cols[2].metric("稀有度", weapon["rarity"])
            info_cols[3].metric("弹药", weapon["ammo_type"])
            info_cols[4].metric("弹匣", weapon["magazine_size"])
            if weapon["quote"]:
                st.caption(weapon["quote"])

            summary_col, stats_col = st.columns([1.2, 1])
            with summary_col:
                st.subheader("概述")
                if weapon["summary"]:
                    for paragraph in weapon["summary"].split("\n\n"):
                        st.write(paragraph)
                else:
                    st.write("无")
                st.subheader("来源")
                if weapon["sources_json"]:
                    for source in weapon["sources_json"]:
                        st.write(f"- {source}")
                else:
                    st.write("无")
                st.subheader("模组槽位")
                if weapon["mod_slots_json"]:
                    st.write(" / ".join(weapon["mod_slots_json"]))
                else:
                    st.write("无")

            with stats_col:
                st.subheader("基础属性")
                stats_df = pd.DataFrame(
                    [{"属性": key, "值": value} for key, value in weapon["stats_json"].items()]
                )
                st.dataframe(stats_df, use_container_width=True, hide_index=True)
                st.subheader("页面链接")
                st.markdown(f"[{weapon['url']}]({weapon['url']})")

            section_tabs = st.tabs(["Crafting", "Upgrading", "Repairing", "Recycling", "Sale Price", "History"])
            section_mappings = [
                ("crafting_json", "暂无 Crafting 数据。"),
                ("upgrading_json", "暂无 Upgrading 数据。"),
                ("repairing_json", "暂无 Repairing 数据。"),
                ("recycling_json", "暂无 Recycling 数据。"),
                ("price_comparison_json", "暂无价格对比数据。"),
                ("history_json", "暂无版本历史数据。"),
            ]
            for tab, (column_name, empty_message) in zip(section_tabs, section_mappings, strict=True):
                with tab:
                    section_df = table_rows_to_dataframe(weapon[column_name])
                    if section_df.empty:
                        st.info(empty_message)
                    else:
                        st.dataframe(section_df, use_container_width=True, hide_index=True)

    with raw_tab:
        if weapons_df.empty:
            st.info("暂无原始数据。")
        else:
            raw_item_id = st.selectbox(
                "查看原始 JSON",
                options=weapons_df["item_id"].tolist(),
                key="raw_weapon_id",
                format_func=lambda item_id: f"{item_id} - {weapons_df.loc[weapons_df['item_id'] == item_id, 'title'].iloc[0]}",
            )
            raw_record = weapons_df[weapons_df["item_id"] == raw_item_id].iloc[0]
            st.json(raw_record["raw_payload_json"])

    with runs_tab:
        if runs_df.empty:
            st.info("暂无运行记录。")
        else:
            st.dataframe(runs_df, use_container_width=True, hide_index=True)
