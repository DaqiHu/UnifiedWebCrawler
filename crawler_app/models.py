from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class JobRecord:
    source: str
    job_id: str
    url: str
    title: str
    location: str
    category: str
    category_id: str
    target_audience: str
    job_nature: str
    job_nature_id: int
    hire_type_name: str
    hire_type_id: int
    project_name: str
    description: str
    requirements: str
    bonus_points: str
    summary: str = ""
    delivery_instructions: str = ""
    address_ids: list[str] = field(default_factory=list)
    channel_detail_ids: list[int] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: str = field(default_factory=utc_now_iso)

    def combined_text(self) -> str:
        parts = [
            self.title,
            self.summary,
            self.description,
            self.requirements,
            self.bonus_points,
            self.delivery_instructions,
            " ".join(self.tags),
        ]
        return "\n".join(part for part in parts if part)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RelatedJob:
    source_job_id: str
    related_job_id: str
    rank_order: int
    related_title: str


@dataclass(slots=True)
class CrawlBundle:
    source: str
    target: str
    primary_job: JobRecord
    related_jobs: list[JobRecord]
    related_links: list[RelatedJob]
    raw_snapshot: dict[str, Any]
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: str = field(default_factory=utc_now_iso)


@dataclass(slots=True)
class WeaponRecord:
    source: str
    item_id: str
    url: str
    title: str
    item_type: str
    rarity: str
    ammo_type: str
    firing_mode: str
    arc_armor_penetration: str
    magazine_size: str
    quote: str = ""
    summary: str = ""
    infobox_tags: list[str] = field(default_factory=list)
    mod_slots: list[str] = field(default_factory=list)
    stats: dict[str, str] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)
    crafting: list[dict[str, str]] = field(default_factory=list)
    upgrading: list[dict[str, str]] = field(default_factory=list)
    repairing: list[dict[str, str]] = field(default_factory=list)
    recycling: list[dict[str, str]] = field(default_factory=list)
    price_comparison: list[dict[str, str]] = field(default_factory=list)
    history: list[dict[str, str]] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class WeaponBundle:
    source: str
    target: str
    primary_weapon: WeaponRecord
    raw_snapshot: dict[str, Any]
    started_at: str = field(default_factory=utc_now_iso)
    finished_at: str = field(default_factory=utc_now_iso)
