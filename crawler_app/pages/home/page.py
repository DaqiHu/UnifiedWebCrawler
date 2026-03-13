from __future__ import annotations

import streamlit as st

from crawler_app.pages.shared import render_page_header


def render_home_page() -> None:
    render_page_header(
        "Unified Web Crawler",
        "把完全独立的需求拆成独立页面。首页只负责路由和目录。",
    )
    st.info("当前已拆分为独立页面：miHoYo 校招岗位分析、ARC Raiders 武器资料抓取、ARC Raiders 怪物资料抓取。")

    columns = st.columns(3)
    with columns[0]:
        st.markdown(
            """
            <div class="route-card">
                <h3>miHoYo 校招岗位</h3>
                <div>招聘岗位抓取、相似岗位、关键词分析与对比。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("进入 miHoYo 页面", key="go_mihoyo", use_container_width=True):
            st.switch_page("pages/1_mihoyo_jobs.py")

    with columns[1]:
        st.markdown(
            """
            <div class="route-card">
                <h3>ARC Raiders 武器资料</h3>
                <div>抓取武器基础属性、来源、制作/升级/修理/回收链路和版本历史。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("进入 ARC Raiders 页面", key="go_arc", use_container_width=True):
            st.switch_page("pages/2_arc_raiders_weapons.py")

    with columns[2]:
        st.markdown(
            """
            <div class="route-card">
                <h3>ARC Raiders 怪物资料</h3>
                <div>抓取 ARC 敌人的威胁等级、弱点、战斗提示、掉落和图鉴信息。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.button("进入 ARC 怪物页面", key="go_arc_enemies", use_container_width=True):
            st.switch_page("pages/3_arc_raiders_arc.py")
