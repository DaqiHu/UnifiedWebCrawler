from __future__ import annotations

from typing import Iterable

import pandas as pd

from crawler_app.config import SKILL_KEYWORDS


def split_non_empty_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def build_skill_summary(jobs_df: pd.DataFrame) -> pd.DataFrame:
    if jobs_df.empty:
        return pd.DataFrame(columns=["skill", "count"])

    records: list[dict[str, object]] = []
    combined = (
        jobs_df["title"].fillna("")
        + "\n"
        + jobs_df["description"].fillna("")
        + "\n"
        + jobs_df["requirements"].fillna("")
        + "\n"
        + jobs_df["bonus_points"].fillna("")
    )

    for skill, keywords in SKILL_KEYWORDS.items():
        count = 0
        for text in combined:
            lowered = text.lower()
            if any(keyword.lower() in lowered for keyword in keywords):
                count += 1
        records.append({"skill": skill, "count": count})

    dataframe = pd.DataFrame(records)
    return dataframe.sort_values(by=["count", "skill"], ascending=[False, True]).reset_index(drop=True)


def build_skill_matrix(jobs_df: pd.DataFrame, selected_job_ids: Iterable[str]) -> pd.DataFrame:
    selected = jobs_df[jobs_df["job_id"].isin(list(selected_job_ids))].copy()
    if selected.empty:
        return pd.DataFrame()

    combined = (
        selected["title"].fillna("")
        + "\n"
        + selected["description"].fillna("")
        + "\n"
        + selected["requirements"].fillna("")
        + "\n"
        + selected["bonus_points"].fillna("")
    )
    for skill, keywords in SKILL_KEYWORDS.items():
        selected[skill] = [
            "是" if any(keyword.lower() in text.lower() for keyword in keywords) else ""
            for text in combined
        ]
    columns = ["job_id", "title", *SKILL_KEYWORDS.keys()]
    return selected[columns].reset_index(drop=True)


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
    enriched["responsibility_count"] = enriched["description"].fillna("").map(lambda text: len(split_non_empty_lines(text)))
    enriched["requirement_count"] = enriched["requirements"].fillna("").map(lambda text: len(split_non_empty_lines(text)))
    enriched["bonus_count"] = enriched["bonus_points"].fillna("").map(lambda text: len(split_non_empty_lines(text)))
    enriched["updated_at"] = pd.to_datetime(enriched["updated_at"], utc=True, errors="coerce")
    return enriched
