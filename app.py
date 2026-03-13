from __future__ import annotations

from crawler_app.config import APP_TITLE
from crawler_app.pages.home.page import render_home_page
from crawler_app.pages.shared import configure_page, inject_shared_styles


configure_page(APP_TITLE)
inject_shared_styles()
render_home_page()
