from __future__ import annotations

from crawler_app.pages.arc_raiders_weapons.page import render_page
from crawler_app.pages.shared import configure_page, inject_shared_styles


configure_page("ARC Raiders 武器资料")
inject_shared_styles()
render_page()
