from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
EXPORT_DIR = DATA_DIR / "exports"
DB_PATH = DATA_DIR / "crawler.sqlite3"

APP_TITLE = "Unified Web Crawler"
DEFAULT_SOURCE = "mihoyo_jobs"
DEFAULT_TARGET = "https://jobs.mihoyo.com/#/campus/position/8123"

MIHOYO_API_BASE = "https://ats.openout.mihoyo.com/ats-portal"
MIHOYO_JOB_URL = "https://jobs.mihoyo.com/#/campus/position/{job_id}"

HTTP_TIMEOUT_SECONDS = 20.0

SKILL_KEYWORDS = {
    "C++": ["C++"],
    "Python": ["Python"],
    "Unity / UE": ["Unity", "UE", "Unreal"],
    "渲染": ["渲染"],
    "动画": ["动画"],
    "物理": ["物理"],
    "图形学": ["图形学"],
    "工具链": ["工具链"],
    "资源管线": ["资源管线"],
    "性能优化": ["性能", "性能优化"],
    "Windows": ["Windows"],
    "Android": ["Android"],
    "iOS": ["iOS"],
    "PlayStation": ["PlayStation"],
    "AIGC / Agent": ["AIGC", "AI Agent", "AI 自动化", "代码大模型"],
    "数学基础": ["数学"],
    "引擎开发": ["引擎"],
}


def ensure_directories() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)
    EXPORT_DIR.mkdir(exist_ok=True)
