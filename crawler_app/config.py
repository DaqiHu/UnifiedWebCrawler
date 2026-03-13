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
ARC_RAIDERS_DEFAULT_TARGET = "https://arcraiders.wiki/wiki/Kettle"

MIHOYO_API_BASE = "https://ats.openout.mihoyo.com/ats-portal"
MIHOYO_JOB_URL = "https://jobs.mihoyo.com/#/campus/position/{job_id}"
ARC_RAIDERS_WIKI_API = "https://arcraiders.wiki/w/api.php"

HTTP_TIMEOUT_SECONDS = 20.0

ANALYSIS_KEYWORDS = {
    "引擎 / 客户端": ["引擎", "客户端", "C++", "跨平台", "性能优化"],
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
    "交互 / 策划": ["交互", "策划", "体验设计", "原型", "Figma", "玩家体验", "操作体验"],
    "设计工具": ["Figma", "PS", "AI", "Photoshop", "Illustrator"],
    "美术 / 原画": ["原画", "美术", "概念设计", "三视图", "审美", "作品集"],
    "机械 / 载具": ["机械", "载具", "枪械", "硬表面", "写实", "材质"],
    "模型制作": ["3Ds Max", "Maya", "模型制作", "贴图"],
    "游戏体验": ["热爱游戏", "游戏经历", "射击游戏", "玩家心理", "交互反馈"],
}


def ensure_directories() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    RAW_DIR.mkdir(exist_ok=True)
    EXPORT_DIR.mkdir(exist_ok=True)
