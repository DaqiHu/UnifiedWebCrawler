from __future__ import annotations

import streamlit as st


def configure_page(page_title: str) -> None:
    st.set_page_config(
        page_title=page_title,
        layout="wide",
        initial_sidebar_state="expanded",
    )


def inject_shared_styles() -> None:
    st.markdown(
        """
        <style>
            .stApp {
                background:
                    radial-gradient(circle at top left, rgba(15, 76, 117, 0.12), transparent 24rem),
                    linear-gradient(180deg, #f8fbff 0%, #eef3f9 100%);
            }
            .source-card, .route-card {
                border: 1px solid rgba(15, 76, 117, 0.15);
                border-radius: 16px;
                padding: 1rem 1.2rem;
                background: rgba(255, 255, 255, 0.92);
                box-shadow: 0 8px 30px rgba(15, 76, 117, 0.08);
                min-height: 126px;
            }
            .source-card h4, .route-card h3 {
                margin: 0 0 0.4rem 0;
            }
            .mono {
                font-family: Consolas, monospace;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_back_home() -> None:
    st.page_link("app.py", label="返回首页")


def render_page_header(title: str, caption: str) -> None:
    st.title(title)
    st.caption(caption)
