from __future__ import annotations

from crawler_app.pages.mihoyo_jobs.page import render_page
from crawler_app.pages.shared import configure_page, inject_shared_styles


configure_page("miHoYo 校招岗位")
inject_shared_styles()
render_page()
