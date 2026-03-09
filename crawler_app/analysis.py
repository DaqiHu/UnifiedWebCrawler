from __future__ import annotations

import re
from itertools import combinations
from typing import Iterable

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
