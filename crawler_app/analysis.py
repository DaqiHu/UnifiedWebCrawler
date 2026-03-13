from __future__ import annotations

import re
from itertools import combinations
from typing import Any, Iterable

import pandas as pd

from crawler_app.config import ANALYSIS_KEYWORDS


CROSS_DOMAIN_KEYWORDS = {
    "技术/工程": ["开发", "引擎", "程序", "技术实现", "工具链", "资源管线", "前端页面", "前端", "系统", "性能", "客户端", "脚本", "Unity", "UE"],
    "策划/交互": ["策划", "交互", "玩法", "需求分析", "体验流程", "原型", "体验设计", "任务设计", "文案策划", "交互规范"],
    "美术/视觉": ["美术", "原画", "视觉", "UI", "特效", "模型制作", "3D模型", "场景模型", "角色模型", "动画", "场景", "角色", "光影", "材质", "概念设计", "三视图"],
    "AI/数据": ["AIGC", "算法", "模型训练", "Diffusion", "LLM", "数据分析", "实验记录", "自动化", "Agent", "ComfyUI", "Prompt"],
    "业务/市场": ["运营", "社媒", "线下活动", "传播", "品牌", "商务", "市场营销", "社区", "投放", "增长"],
    "法务/合规": ["法务", "合规", "合同", "知识产权", "隐私", "风险", "法律"],
    "国际化/语言": ["英文", "日语", "韩语", "多语言", "本地化", "国际化"],
}

PREP_MATERIAL_KEYWORDS = {
    "作品集/作品附件": ["作品集", "作品", "附件", "PDF", "PNG", "MP4", "ArtStation", "作品橱窗"],
    "游戏经历说明": ["游戏经历", "游戏时长", "游戏相关成就", "资深游戏玩家"],
    "案例/题目准备": ["案例", "最得意的技术实现", "活动经历", "为什么适合这个岗位", "思路", "收获和遗憾"],
    "主页/平台链接": ["主页链接", "Bilibili", "Weibo", "小红书", "社交平台"],
}

TEST_KEYWORDS = ["测试", "笔试", "机试", "作业", "试题", "challenge"]

CROSS_DOMAIN_BRIDGE_KEYWORDS = [
    "工具链",
    "资源管线",
    "跨平台",
    "工作流",
    "前端页面",
    "全链路",
    "完整流程",
    "Unity",
    "UE",
    "AIGC",
]

PIPELINE_STAGE_KEYWORDS = {
    "策划/需求": ["策划", "需求分析", "玩法", "任务", "原型", "方案设计", "交互规范", "体验流程"],
    "美术/内容": ["美术", "原画", "模型制作", "3D模型", "场景模型", "角色模型", "特效", "动画", "场景", "角色", "UI", "资产制作", "概念设计"],
    "技术/工程": ["开发", "引擎", "程序", "前端", "工具链", "系统", "脚本", "算法", "管线", "性能", "Unity", "UE"],
    "质量/验证": ["测试", "验收", "质量", "稳定性", "调优", "验证", "反馈"],
    "运营/发行": ["运营", "社媒", "传播", "线下活动", "品牌", "社区", "投放", "增长", "玩家运营"],
    "职能/合规": ["法务", "合规", "合同", "财务", "税务", "知识产权", "隐私", "采购"],
}

PIPELINE_COLLABORATION_KEYWORDS = [
    "跨多岗位协作",
    "协作",
    "合作",
    "上下游",
    "跟进开发进度",
    "跟进",
    "推进迭代",
    "落地",
    "全链路",
    "完整流程",
    "研发上下游",
    "跨平台",
    "业务部门",
    "沟通",
]

PIPELINE_STAGE_ORDER = [
    "策划/需求",
    "美术/内容",
    "技术/工程",
    "质量/验证",
    "运营/发行",
    "职能/合规",
]

AI_FOCUS_COLUMNS = [
    "job_id",
    "title",
    "category",
    "ai_focus_score",
    "ai_focus_level",
    "ai_focus_lane",
    "ai_focus_reason",
    "ai_analysis",
    "ai_focus_signals_json",
    "ai_focus_updated_at",
]

AI_FOCUS_CATEGORY_BASE = {
    "产品策划类": 18,
    "程序&技术类": 8,
    "美术&表现类": 6,
    "质量管理类": 6,
    "运营类": 5,
    "市场&商务类": 4,
    "国际化类": 4,
    "综合类": 2,
}

AI_FOCUS_DIRECT_TITLE_SCORES = {
    "系统策划": 64,
    "战斗策划": 60,
    "技术策划": 59,
    "数值策划": 58,
    "关卡策划": 56,
    "任务策划": 55,
    "交互策划": 48,
    "文案策划": 34,
}

AI_FOCUS_ADJACENT_TITLE_SCORES = {
    "游戏引擎开发": 30,
    "关卡美术": 22,
    "技术美术": 20,
    "游戏项目管理": 18,
    "用户研究": 18,
    "游戏测试": 14,
    "游戏客户端工具开发": 14,
}

AI_FOCUS_OFF_TARGET_TITLE_SCORES = {
    "AI产品": -14,
    "产品经理": -12,
    "策略产品": -12,
    "数据AI产品": -10,
    "运营": -16,
    "市场": -18,
    "品牌": -18,
    "社媒": -18,
    "法务": -22,
    "财务": -22,
    "税务": -22,
    "采购": -20,
    "人力": -22,
    "行政": -22,
    "合规": -22,
    "大语言模型": -12,
    "训练师": -14,
}

AI_FOCUS_CORE_SIGNALS = [
    "系统架构",
    "系统设计",
    "系统",
    "活动玩法",
    "核心玩法",
    "玩法",
    "机制",
    "体验",
    "体验流程",
    "交互反馈",
    "任务流程",
    "任务逻辑",
    "关卡体验",
    "关卡逻辑",
    "白盒",
    "玩法定位",
    "角色属性",
    "技能效果",
    "战斗数值",
    "经济系统",
    "功能文档",
    "原型",
    "Demo",
    "demo",
    "脚本",
    "配置",
    "方案逻辑",
    "验收",
    "迭代",
]

AI_FOCUS_BRIDGE_SIGNALS = [
    "程序",
    "美术",
    "UI",
    "跟进开发",
    "开发进度",
    "落地",
    "工具",
    "编辑器",
    "引擎",
    "代码",
    "可交互",
    "制作管线",
    "流程",
    "协作",
]

AI_FOCUS_OFF_TARGET_SIGNALS = [
    "投放",
    "广告",
    "社媒",
    "营销",
    "法务",
    "财务",
    "税务",
    "采购",
    "合规",
    "人力资源",
    "品牌",
    "舆情",
    "增长",
    "数据标注",
    "训练数据",
    "大模型",
    "LLM",
    "Prompt",
    "AIGC",
]

AI_FOCUS_CURATED_PROFILES = {
    "系统策划实习生": {
        "score": 98,
        "lane": "策划核心",
        "reason": "直接写到系统架构、功能文档、制作验收与版本迭代，是最贴近游戏系统核心构成的岗位之一。",
        "analysis": (
            "这是当前样本里最值得优先投的岗位之一。JD 直接把你放进“系统架构 -> 功能文档 -> 制作验收 -> "
            "线上迭代”的链路里，日常极容易听到“XX系统”“功能模块”“机制”“体验问题”“版本反馈”这类策划核心术语。"
            "如果你的目标是借求职去听懂策划团队现在到底在怎么拆系统、怎么谈体验，这是最直达核心的位置。"
        ),
        "signals": ["系统架构", "功能文档", "活动玩法", "验收", "版本迭代"],
    },
    "战斗策划实习生": {
        "score": 96,
        "lane": "策划核心",
        "reason": "角色、怪物、枪械、3C、技能、数值与关卡玩法都在同一条职责链上，策划专有名词密度极高。",
        "analysis": (
            "这类岗位会让你持续接触战斗设计最核心的话语体系。JD 里已经出现了角色、怪物、枪械、3C、技能、AI、"
            "数值、关卡玩法、机制需求、方案逻辑这些关键词，说明你会经常听到关于战斗循环、手感、机制耦合与表现落地的讨论。"
            "如果你想听到策划内部最“黑话密集”的讨论，它几乎稳居第一梯队。"
        ),
        "signals": ["角色/怪物", "枪械", "3C", "技能", "数值", "关卡玩法", "机制"],
    },
    "技术策划实习生": {
        "score": 95,
        "lane": "策划核心",
        "reason": "会在玩法创意、原型验证、工具编辑器和逻辑实现层之间来回穿梭，是策划与程序的核心桥位。",
        "analysis": (
            "如果你想同时听懂策划在说什么、程序又是怎么把它实现出来，技术策划非常合适。JD 明确写到“核心玩法前期技术验证”、"
            "“可交互 demo”、“工具与编辑器”、“逻辑实现层”、“设计意图和玩家体验”，这意味着你会长期站在策划术语和工程术语的交界处。"
            "它不一定比系统策划更纯，但非常利于你建立对一个系统如何从概念变成可玩内容的整体认知。"
        ),
        "signals": ["核心玩法", "可交互demo", "工具与编辑器", "逻辑实现层", "玩家体验"],
    },
    "数值策划实习生": {
        "score": 93,
        "lane": "策划核心",
        "reason": "直接覆盖战斗数值、经济系统、角色属性、技能效果与玩家反馈，是系统底层规则讨论的核心岗位。",
        "analysis": (
            "数值策划会把你拉进游戏底层规则的讨论里。JD 明写战斗数值、经济系统、角色属性、技能效果、怪物强度、资源循环，"
            "这类岗位最容易听到“成长曲线”“资源投放”“经济闭环”“平衡”“强度”“策略深度”等设计术语。"
            "如果你想理解系统为什么这样运转，而不是只看表面体验，这个方向非常强。"
        ),
        "signals": ["战斗数值", "经济系统", "角色属性", "技能效果", "资源循环"],
    },
    "关卡策划实习生": {
        "score": 91,
        "lane": "策划核心",
        "reason": "关卡体验、流程、逻辑、白盒和原型都直接写进职责，对“体验设计”类词汇非常敏感。",
        "analysis": (
            "关卡策划是另一个高命中岗位。你会长期围绕“关卡体验”“流程”“逻辑”“白盒”“原型”“落地”这些概念工作，"
            "而且还要和程序、美术一起推进实现。相比系统策划，它更偏空间、流程和节奏；相比任务策划，它更偏玩法承载和关卡结构。"
            "如果你想听大量关于体验节奏、引导、空间组织的讨论，它很合适。"
        ),
        "signals": ["关卡体验", "流程", "关卡逻辑", "白盒", "原型"],
    },
    "任务策划实习生": {
        "score": 90,
        "lane": "策划核心",
        "reason": "会持续讨论任务流程、逻辑框架、引导性、自由度、情绪节奏和玩法融合，属于设计核心岗位。",
        "analysis": (
            "任务策划虽然不像战斗策划那样偏机制黑话，但它对“体验结构”的理解很深。JD 里写到了任务流程、逻辑框架、引导性、"
            "自由度、惊喜感、情绪节奏、剧情与玩法融合，这说明你会大量接触设计团队如何塑造玩家体验。"
            "如果你想听到“体验”“节奏”“引导”“叙事与玩法融合”这类策划术语，它是高优先级选项。"
        ),
        "signals": ["任务流程", "逻辑框架", "引导性", "自由度", "情绪节奏"],
    },
    "交互策划（UE）实习生": {
        "score": 84,
        "lane": "策划核心",
        "reason": "偏界面与交互体验，但仍然直接写到需求分析、体验流程、交互规范、验收和迭代。",
        "analysis": (
            "这个岗位比系统/战斗/数值更偏界面与交互，但仍然是在策划语境里工作。JD 写到需求分析、体验流程、操作体验、反馈、"
            "交互规范、验收和迭代，所以你会频繁听到“流程”“反馈”“体验问题”“规范”“落地”等讨论。"
            "如果你更关心玩家感知层面的设计语言，这个岗位非常值得投。"
        ),
        "signals": ["需求分析", "体验流程", "操作体验", "交互反馈", "验收", "迭代"],
    },
    "文案策划实习生": {
        "score": 68,
        "lane": "策划外围",
        "reason": "能接触内容包装和脚本配置，但离系统机制和玩法核心更远。",
        "analysis": (
            "文案策划也能接触策划团队，只是更偏内容表达而不是系统构成。你会更多听到剧情、设定、文本包装、脚本配置、角色与怪物内容等话题，"
            "对理解“系统/机制”帮助不如系统、战斗、数值、技术这些岗位直接。若你的目标是听设计核心术语，它可以作为补充，不建议作为第一优先。"
        ),
        "signals": ["剧情", "设定", "脚本配置", "内容包装"],
    },
    "游戏引擎开发实习生": {
        "score": 63,
        "lane": "策划-技术桥梁",
        "reason": "非常接近系统底层实现，但更多听到的是引擎与工具链语言，而不是策划讨论本身。",
        "analysis": (
            "这个岗位会让你接触系统“怎么做出来”，但不一定能让你持续听到策划怎么定义体验。JD 重点在动画系统、物理模拟、资源管线、工具链、"
            "跨平台和性能优化，所以你更容易听到工程核心词，而不是“机制/体验/玩法结构”的内部讨论。"
            "如果你想理解系统底层构成，它很有价值；如果你主要想贴近策划黑话，它适合作为侧面观察位，不是首选。"
        ),
        "signals": ["动画系统", "物理模拟", "资源管线", "工具链", "性能优化"],
    },
    "关卡美术实习生": {
        "score": 58,
        "lane": "策划外围",
        "reason": "会和策划一起规划场景与关卡落地，但主要还是从美术资源和环境氛围角度参与。",
        "analysis": (
            "关卡美术能让你侧面听到关卡讨论，因为 JD 明写了与策划一起规划场景人文、生态、水系、景点等内容，并跟进最终落地效果。"
            "但你接触这些内容的入口仍然是美术资源和环境氛围，而不是关卡逻辑或机制定义本身。"
            "如果你想从内容落地反推策划思路，它可以作为补充样本。"
        ),
        "signals": ["关卡落地", "场景规划", "生态", "环境氛围"],
    },
    "技术美术实习生（多方向）": {
        "score": 56,
        "lane": "策划-技术桥梁",
        "reason": "主要在美术管线和技术验证层，与策划核心机制讨论有交集，但不是主战场。",
        "analysis": (
            "技术美术会让你看到内容生产如何被技术方案支撑起来，尤其是管线、工具、性能、新效果验证这些环节。"
            "它能帮助你理解一个系统的内容如何被批量生产和优化，但你听到的更多会是美术和技术的接口语言，而不是策划最核心的机制讨论。"
        ),
        "signals": ["美术管线", "工具", "技术验证", "性能分析", "优化方案"],
    },
    "游戏项目管理实习生": {
        "score": 52,
        "lane": "侧面观察",
        "reason": "能看到全流程协作和信息流，但主要听到排期、流程和风险，而不是具体的设计术语。",
        "analysis": (
            "项目管理适合看清一家公司怎么运转，但不适合专门听策划黑话。你会更多接触流程推进、需求排期、复盘、风险预警、信息流通和上下游协作。"
            "它能帮你建立全局视角，却离“系统/机制/体验拆解”这类核心设计讨论有一层距离。"
        ),
        "signals": ["全流程管理", "需求排期", "流程优化", "上下游协作"],
    },
    "用户研究实习生": {
        "score": 54,
        "lane": "侧面观察",
        "reason": "会接触玩家体验反馈和研究结论，但通常不是定义系统机制的岗位。",
        "analysis": (
            "用户研究能让你听到很多关于‘体验问题’和‘玩家反馈’的讨论，但它更像是站在外侧观察设计结果，而不是直接参与系统定义。"
            "如果你想理解团队现在在关注哪些体验问题，它有价值；如果你想听‘XX系统该怎么做’，它不是最直接的位置。"
        ),
        "signals": ["核心玩法", "体验反馈", "研究方案", "数据分析"],
    },
}


def split_non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def build_skill_summary(jobs_df: pd.DataFrame) -> pd.DataFrame:
    if jobs_df.empty:
        return pd.DataFrame(columns=["topic", "count"])

    records: list[dict[str, object]] = []
    combined = build_combined_series(jobs_df)

    for topic, keywords in ANALYSIS_KEYWORDS.items():
        count = 0
        for text in combined:
            lowered = text.lower()
            if any(keyword.lower() in lowered for keyword in keywords):
                count += 1
        records.append({"topic": topic, "count": count})

    dataframe = pd.DataFrame(records)
    return dataframe.sort_values(by=["count", "topic"], ascending=[False, True]).reset_index(drop=True)


def build_skill_matrix(jobs_df: pd.DataFrame, selected_job_ids: Iterable[str]) -> pd.DataFrame:
    selected = jobs_df[jobs_df["job_id"].isin(list(selected_job_ids))].copy()
    if selected.empty:
        return pd.DataFrame()

    combined = build_combined_series(selected)
    for topic, keywords in ANALYSIS_KEYWORDS.items():
        selected[topic] = [
            "是" if any(keyword.lower() in text.lower() for keyword in keywords) else ""
            for text in combined
        ]
    columns = ["job_id", "title", "category", "tags_text", *ANALYSIS_KEYWORDS.keys()]
    return selected[columns].reset_index(drop=True)


def build_focus_insights(jobs_df: pd.DataFrame) -> dict[str, object]:
    cross_domain_df = build_cross_domain_candidates(jobs_df, limit=15)
    low_prep_df = build_low_prep_candidates(jobs_df, limit=12)
    pipeline_df = build_pipeline_visibility_candidates(jobs_df, limit=15)
    edges_df = build_pipeline_edge_summary(jobs_df, limit=8)

    cross_titles = _preferred_title_summary(
        cross_domain_df,
        ["游戏引擎开发实习生", "交互策划（UE）实习生", "AIGC视觉算法实习生-崩坏：因缘精灵", "系统策划实习生"],
    )
    low_prep_titles = _preferred_title_summary(
        low_prep_df,
        ["策略产品实习生（搜推方向）", "AI产品实习生", "AI人文训练师实习生", "AI产品经理实习生（国际化社媒方向）"],
    )
    pipeline_titles = _preferred_title_summary(
        pipeline_df,
        ["系统策划实习生", "交互策划（UE）实习生", "游戏引擎开发实习生", "关卡美术实习生"],
    )
    edge_titles = "、".join(edges_df["edge"].head(3).tolist()) if not edges_df.empty else "暂无明确样本"

    return {
        "cross_domain": {
            "description": "找同时覆盖多个职能语义簇的岗位，优先看技术、美术、策划、AI、市场、法务等信号是否同时出现。",
            "summary": f"当前最明显的跨界融合岗位集中在 {cross_titles}。",
            "table": cross_domain_df,
        },
        "low_prep": {
            "description": "这里衡量的是投递前准备负担，不是岗位难度。优先筛没有额外材料、没有公开测试说明、投递说明较短的岗位。",
            "summary": f"当前公开 JD 中前置准备相对轻的岗位主要是 {low_prep_titles}。",
            "table": low_prep_df,
        },
        "pipeline": {
            "description": "优先看同时命中多个生产环节且职责写到协作、上下游、落地、验收、全链路的岗位，这类岗位最适合反推公司生产管线。",
            "summary": f"最适合拿来画公司管线拓扑的岗位包括 {pipeline_titles}；高频连接边目前是 {edge_titles}。",
            "table": pipeline_df,
            "edges": edges_df,
        },
    }


def build_ai_focus_dataframe(jobs_df: pd.DataFrame) -> pd.DataFrame:
    if jobs_df.empty:
        return pd.DataFrame(columns=AI_FOCUS_COLUMNS)

    working_df = enrich_jobs_dataframe(jobs_df)
    records = [_build_ai_focus_record(row) for row in working_df.to_dict("records")]
    dataframe = pd.DataFrame(records)
    if dataframe.empty:
        return pd.DataFrame(columns=AI_FOCUS_COLUMNS)

    return (
        dataframe[AI_FOCUS_COLUMNS]
        .sort_values(by=["ai_focus_score", "title", "job_id"], ascending=[False, True, True])
        .reset_index(drop=True)
    )


def build_overview_metrics(jobs_df: pd.DataFrame) -> dict[str, int]:
    if jobs_df.empty:
        return {
            "jobs": 0,
            "locations": 0,
            "categories": 0,
            "internships": 0,
        }

    return {
        "jobs": int(jobs_df["job_id"].nunique()),
        "locations": int(jobs_df["location"].nunique()),
        "categories": int(jobs_df["category"].nunique()),
        "internships": int((jobs_df["job_nature"] == "实习").sum()),
    }


def enrich_jobs_dataframe(jobs_df: pd.DataFrame) -> pd.DataFrame:
    if jobs_df.empty:
        return jobs_df

    enriched = jobs_df.copy()
    enriched["summary_count"] = enriched["summary"].fillna("").map(lambda text: len(split_non_empty_lines(text)))
    enriched["responsibility_count"] = enriched["description"].fillna("").map(lambda text: len(split_non_empty_lines(text)))
    enriched["requirement_count"] = enriched["requirements"].fillna("").map(lambda text: len(split_non_empty_lines(text)))
    enriched["bonus_count"] = enriched["bonus_points"].fillna("").map(lambda text: len(split_non_empty_lines(text)))
    enriched["delivery_count"] = enriched["delivery_instructions"].fillna("").map(lambda text: len(split_non_empty_lines(text)))
    enriched["tags_text"] = enriched["tags_json"].map(lambda tags: " / ".join(tags) if isinstance(tags, list) else "")
    enriched["updated_at"] = pd.to_datetime(enriched["updated_at"], utc=True, errors="coerce")
    return enriched


def build_category_summary(jobs_df: pd.DataFrame) -> pd.DataFrame:
    if jobs_df.empty:
        return pd.DataFrame(columns=["category", "count"])
    return (
        jobs_df.groupby("category", as_index=False)["job_id"]
        .count()
        .rename(columns={"job_id": "count"})
        .sort_values(by=["count", "category"], ascending=[False, True])
        .reset_index(drop=True)
    )


def build_tag_summary(jobs_df: pd.DataFrame) -> pd.DataFrame:
    if jobs_df.empty:
        return pd.DataFrame(columns=["tag", "count"])

    exploded = jobs_df[["job_id", "tags_json"]].explode("tags_json")
    exploded = exploded[exploded["tags_json"].notna() & (exploded["tags_json"] != "")]
    if exploded.empty:
        return pd.DataFrame(columns=["tag", "count"])
    return (
        exploded.groupby("tags_json", as_index=False)["job_id"]
        .count()
        .rename(columns={"tags_json": "tag", "job_id": "count"})
        .sort_values(by=["count", "tag"], ascending=[False, True])
        .reset_index(drop=True)
    )


def build_combined_series(jobs_df: pd.DataFrame) -> pd.Series:
    tags_series = jobs_df["tags_text"] if "tags_text" in jobs_df.columns else ""
    return (
        jobs_df["title"].fillna("")
        + "\n"
        + jobs_df["summary"].fillna("")
        + "\n"
        + jobs_df["description"].fillna("")
        + "\n"
        + jobs_df["requirements"].fillna("")
        + "\n"
        + jobs_df["bonus_points"].fillna("")
        + "\n"
        + jobs_df["delivery_instructions"].fillna("")
        + "\n"
        + (tags_series.fillna("") if hasattr(tags_series, "fillna") else "")
    )


def _build_ai_focus_record(row: dict[str, Any]) -> dict[str, Any]:
    title = str(row.get("title", "") or "")
    category = str(row.get("category", "") or "")
    combined_text = "\n".join(
        [
            title,
            str(row.get("summary", "") or ""),
            str(row.get("description", "") or ""),
            str(row.get("requirements", "") or ""),
            str(row.get("bonus_points", "") or ""),
            str(row.get("delivery_instructions", "") or ""),
            str(row.get("tags_text", "") or ""),
        ]
    )

    curated = AI_FOCUS_CURATED_PROFILES.get(title)
    core_hits = _match_keywords(combined_text, AI_FOCUS_CORE_SIGNALS)
    bridge_hits = _match_keywords(combined_text, AI_FOCUS_BRIDGE_SIGNALS)
    off_target_hits = _match_keywords(combined_text, AI_FOCUS_OFF_TARGET_SIGNALS)

    if curated:
        score = int(curated["score"])
        lane = str(curated["lane"])
        reason = str(curated["reason"])
        analysis = str(curated["analysis"])
        signals = _dedupe_preserve_order([*curated.get("signals", []), *core_hits[:4], *bridge_hits[:3]])
    else:
        score = AI_FOCUS_CATEGORY_BASE.get(category, 4)
        score += _match_title_score(title, AI_FOCUS_DIRECT_TITLE_SCORES)
        score += _match_title_score(title, AI_FOCUS_ADJACENT_TITLE_SCORES)
        score += _match_title_score(title, AI_FOCUS_OFF_TARGET_TITLE_SCORES)
        score += min(len(core_hits), 8) * 4
        score += min(len(bridge_hits), 6) * 2
        score -= min(len(off_target_hits), 5) * 3
        score = max(0, min(100, score))
        lane = _focus_lane_from_score(score)
        reason = _build_focus_reason(title, category, core_hits, bridge_hits, off_target_hits, lane)
        analysis = _build_focus_analysis(title, lane, core_hits, bridge_hits, off_target_hits)
        signals = _dedupe_preserve_order([*core_hits[:5], *bridge_hits[:3], *off_target_hits[:2]])

    level = _focus_level_from_score(score)
    return {
        "job_id": str(row.get("job_id", "") or ""),
        "title": title,
        "category": category,
        "ai_focus_score": score,
        "ai_focus_level": level,
        "ai_focus_lane": lane,
        "ai_focus_reason": reason,
        "ai_analysis": analysis,
        "ai_focus_signals_json": signals,
        "ai_focus_updated_at": pd.Timestamp.utcnow().isoformat(),
    }


def build_cross_domain_candidates(jobs_df: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    if jobs_df.empty:
        return pd.DataFrame(columns=["job_id", "title", "category", "cross_domain_score", "matched_domains", "reason"])

    combined = build_combined_series(jobs_df)
    records: list[dict[str, object]] = []
    for row, text in zip(jobs_df.to_dict("records"), combined, strict=False):
        matched_domains = _match_topics(str(text), CROSS_DOMAIN_KEYWORDS)
        collaboration_hits = _match_keywords(str(text), PIPELINE_COLLABORATION_KEYWORDS)
        bridge_hits = _match_keywords(str(text), CROSS_DOMAIN_BRIDGE_KEYWORDS)
        if len(matched_domains) < 2:
            continue

        score = len(matched_domains) * 3 + min(len(collaboration_hits), 2) + min(len(bridge_hits), 5)
        reason_parts = [f"覆盖 {len(matched_domains)} 个领域: {' / '.join(matched_domains)}"]
        if bridge_hits:
            reason_parts.append(f"桥接信号: {' / '.join(bridge_hits[:3])}")
        if collaboration_hits:
            reason_parts.append(f"协作信号: {' / '.join(collaboration_hits[:3])}")
        records.append(
            {
                "job_id": row["job_id"],
                "title": row["title"],
                "category": row["category"],
                "cross_domain_score": score,
                "matched_domains": " / ".join(matched_domains),
                "reason": "；".join(reason_parts),
            }
        )

    dataframe = pd.DataFrame(records)
    if dataframe.empty:
        return pd.DataFrame(columns=["job_id", "title", "category", "cross_domain_score", "matched_domains", "reason"])
    return (
        dataframe.sort_values(
            by=["cross_domain_score", "category", "job_id"],
            ascending=[False, True, True],
        )
        .head(limit)
        .reset_index(drop=True)
    )


def build_low_prep_candidates(jobs_df: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    if jobs_df.empty:
        return pd.DataFrame(
            columns=["job_id", "title", "category", "prep_burden_score", "explicit_tests", "extra_materials", "reason"]
        )

    records: list[dict[str, object]] = []
    for row in jobs_df.to_dict("records"):
        delivery_text = str(row.get("delivery_instructions", "") or "")
        requirement_text = str(row.get("requirements", "") or "")
        combined_text = "\n".join([delivery_text, requirement_text, str(row.get("summary", "") or "")])
        material_hits = _match_topic_labels(delivery_text, PREP_MATERIAL_KEYWORDS)
        mandatory_hits = _match_keywords(delivery_text, ["必需项", "请务必", "请附上", "请准备好", "请简单描述"])
        test_hits = _match_keywords(combined_text, TEST_KEYWORDS)
        delivery_lines = len(split_non_empty_lines(delivery_text))
        prep_burden_score = len(material_hits) * 3 + len(mandatory_hits) * 2 + len(test_hits) * 4 + max(delivery_lines - 1, 0)

        if prep_burden_score > 8:
            continue

        if prep_burden_score == 0:
            reason = "未看到额外投递材料、公开测试或补充说明要求。"
        else:
            reason_parts = []
            if material_hits:
                reason_parts.append(f"额外材料: {' / '.join(material_hits)}")
            if test_hits:
                reason_parts.append(f"测试信号: {' / '.join(test_hits)}")
            if mandatory_hits:
                reason_parts.append(f"强制提示: {' / '.join(mandatory_hits)}")
            reason = "；".join(reason_parts)

        records.append(
            {
                "job_id": row["job_id"],
                "title": row["title"],
                "category": row["category"],
                "prep_burden_score": prep_burden_score,
                "explicit_tests": " / ".join(test_hits) if test_hits else "无",
                "extra_materials": " / ".join(material_hits) if material_hits else "无",
                "reason": reason,
            }
        )

    dataframe = pd.DataFrame(records)
    if dataframe.empty:
        return pd.DataFrame(
            columns=["job_id", "title", "category", "prep_burden_score", "explicit_tests", "extra_materials", "reason"]
        )
    return (
        dataframe.sort_values(
            by=["prep_burden_score", "category", "job_id"],
            ascending=[True, True, True],
        )
        .head(limit)
        .reset_index(drop=True)
    )


def build_pipeline_visibility_candidates(jobs_df: pd.DataFrame, limit: int = 8) -> pd.DataFrame:
    if jobs_df.empty:
        return pd.DataFrame(
            columns=["job_id", "title", "category", "pipeline_visibility_score", "bridge_path", "reason"]
        )

    combined = build_combined_series(jobs_df)
    records: list[dict[str, object]] = []
    for row, text in zip(jobs_df.to_dict("records"), combined, strict=False):
        matched_stages = _ordered_matches(_match_topics(str(text), PIPELINE_STAGE_KEYWORDS), PIPELINE_STAGE_ORDER)
        collaboration_hits = _match_keywords(str(text), PIPELINE_COLLABORATION_KEYWORDS)
        if len(matched_stages) < 2 and len(collaboration_hits) < 2:
            continue

        score = len(matched_stages) * 2 + min(len(collaboration_hits), 4)
        if any(keyword in str(text) for keyword in ["全链路", "完整流程", "上下游", "工具链", "资源管线"]):
            score += 2
        reason_parts = []
        if matched_stages:
            reason_parts.append(f"覆盖环节: {' -> '.join(matched_stages)}")
        if collaboration_hits:
            reason_parts.append(f"协作线索: {' / '.join(collaboration_hits[:4])}")
        records.append(
            {
                "job_id": row["job_id"],
                "title": row["title"],
                "category": row["category"],
                "pipeline_visibility_score": score,
                "bridge_path": " -> ".join(matched_stages),
                "reason": "；".join(reason_parts),
            }
        )

    dataframe = pd.DataFrame(records)
    if dataframe.empty:
        return pd.DataFrame(
            columns=["job_id", "title", "category", "pipeline_visibility_score", "bridge_path", "reason"]
        )
    return (
        dataframe.sort_values(
            by=["pipeline_visibility_score", "category", "job_id"],
            ascending=[False, True, True],
        )
        .head(limit)
        .reset_index(drop=True)
    )


def build_pipeline_edge_summary(jobs_df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    if jobs_df.empty:
        return pd.DataFrame(columns=["edge", "count", "example_jobs"])

    combined = build_combined_series(jobs_df)
    edge_map: dict[tuple[str, str], list[str]] = {}
    for row, text in zip(jobs_df.to_dict("records"), combined, strict=False):
        matched_stages = _ordered_matches(_match_topics(str(text), PIPELINE_STAGE_KEYWORDS), PIPELINE_STAGE_ORDER)
        if len(matched_stages) < 2:
            continue
        for left, right in combinations(matched_stages, 2):
            edge_map.setdefault((left, right), []).append(str(row["title"]))

    records = []
    for edge, titles in edge_map.items():
        records.append(
            {
                "edge": f"{edge[0]} <-> {edge[1]}",
                "count": len(titles),
                "example_jobs": " / ".join(titles[:3]),
            }
        )

    dataframe = pd.DataFrame(records)
    if dataframe.empty:
        return pd.DataFrame(columns=["edge", "count", "example_jobs"])
    return dataframe.sort_values(by=["count", "edge"], ascending=[False, True]).head(limit).reset_index(drop=True)


def _match_topics(text: str, keyword_map: dict[str, list[str]]) -> list[str]:
    matched = []
    for label, keywords in keyword_map.items():
        if any(_contains_keyword(text, keyword) for keyword in keywords):
            matched.append(label)
    return matched


def _match_topic_labels(text: str, keyword_map: dict[str, list[str]]) -> list[str]:
    matched = []
    for label, keywords in keyword_map.items():
        if any(_contains_keyword(text, keyword) for keyword in keywords):
            matched.append(label)
    return matched


def _match_keywords(text: str, keywords: Iterable[str]) -> list[str]:
    return [keyword for keyword in keywords if _contains_keyword(text, keyword)]


def _ordered_matches(values: list[str], order: list[str]) -> list[str]:
    order_map = {value: index for index, value in enumerate(order)}
    return sorted(values, key=lambda value: order_map.get(value, 10_000))


def _contains_keyword(text: str, keyword: str) -> bool:
    if not keyword:
        return False
    if any(character.isascii() and character.isalnum() for character in keyword):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])", re.IGNORECASE)
        return bool(pattern.search(text))
    return keyword.lower() in text.lower()


def _preferred_title_summary(dataframe: pd.DataFrame, preferred_titles: list[str], fallback_count: int = 3) -> str:
    if dataframe.empty:
        return "暂无明确样本"

    available_titles = dataframe["title"].tolist()
    selected_titles = [title for title in preferred_titles if title in available_titles]
    if not selected_titles:
        selected_titles = available_titles[:fallback_count]
    return "、".join(selected_titles[:fallback_count])


def _match_title_score(title: str, score_map: dict[str, int]) -> int:
    total = 0
    for keyword, score in score_map.items():
        if _contains_keyword(title, keyword):
            total += score
    return total


def _focus_level_from_score(score: int) -> str:
    if score >= 90:
        return "极高"
    if score >= 75:
        return "高"
    if score >= 55:
        return "中"
    return "低"


def _focus_lane_from_score(score: int) -> str:
    if score >= 82:
        return "策划核心"
    if score >= 60:
        return "策划-技术桥梁"
    if score >= 45:
        return "策划外围"
    return "侧面观察"


def _build_focus_reason(
    title: str,
    category: str,
    core_hits: list[str],
    bridge_hits: list[str],
    off_target_hits: list[str],
    lane: str,
) -> str:
    if lane == "策划核心":
        if core_hits:
            return f"岗位本身就贴近设计核心，并且 JD 明确出现 { ' / '.join(core_hits[:4]) } 等信号。"
        return "岗位标题和职责都更接近系统、玩法、体验或数值的定义层。"
    if lane == "策划-技术桥梁":
        if bridge_hits:
            return f"能看到系统如何落地，但更偏实现桥梁，主要信号包括 { ' / '.join(bridge_hits[:4]) }。"
        return "更适合理解系统实现或协作接口，而不是直接参与策划核心定义。"
    if lane == "策划外围":
        if off_target_hits:
            return f"能接触部分设计话题，但更多注意力会被 { ' / '.join(off_target_hits[:3]) } 等非核心议题分走。"
        return "与策划有协作面，但主要不是围绕系统机制本身展开。"
    if off_target_hits:
        return f"更偏 {category} 或其他职能语境，JD 重点落在 { ' / '.join(off_target_hits[:4]) }。"
    return f"{title} 更像是从外围观察游戏生产，而不是直接听策划讨论系统与机制。"


def _build_focus_analysis(
    title: str,
    lane: str,
    core_hits: list[str],
    bridge_hits: list[str],
    off_target_hits: list[str],
) -> str:
    if lane == "策划核心":
        focus_terms = "、".join(core_hits[:5]) if core_hits else "系统、机制、体验和迭代"
        return (
            f"{title} 属于直接接触游戏设计核心的岗位。你大概率会频繁听到 {focus_terms} 这类词，"
            "因为岗位本身就在定义玩法结构、体验目标或系统规则。对你当前“想通过求职去听懂策划真正关注什么”的目标，它是优先级很高的选择。"
        )
    if lane == "策划-技术桥梁":
        bridge_terms = "、".join((core_hits + bridge_hits)[:5]) or "实现、工具、流程和落地"
        return (
            f"{title} 更适合帮助你理解设计是怎么被做出来的。你会接触 {bridge_terms} 这类讨论，"
            "能看到系统核心构成，但听到的术语会混合大量实现层语言，因此更像第二梯队选择。"
        )
    if lane == "策划外围":
        side_terms = "、".join((core_hits + bridge_hits)[:4]) or "协作、落地和内容表达"
        return (
            f"{title} 能让你部分接触策划讨论，但更多是从 {side_terms} 这些外围切面进入。"
            "如果你的首要目标是听到策划团队密集讨论机制和系统，它可以作为补充，不建议排在第一批。"
        )
    off_terms = "、".join(off_target_hits[:4]) or "运营、职能或其他非设计议题"
    return (
        f"{title} 与你的目标有明显距离。岗位重点更偏 {off_terms}，"
        "即使会碰到游戏相关语境，也不太会高频进入策划团队关于系统、机制和体验结构的核心讨论。"
    )


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        if value and value not in deduped:
            deduped.append(value)
    return deduped
