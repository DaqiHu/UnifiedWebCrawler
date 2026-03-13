from __future__ import annotations

from datetime import datetime, timezone

from crawler_app.analysis import build_ai_focus_dataframe, enrich_jobs_dataframe
from crawler_app.config import ARC_RAIDERS_ARC_OVERVIEW_PAGE, ARC_RAIDERS_WEAPON_CATEGORY
from crawler_app.connectors import get_connectors
from crawler_app.connectors.arc_raiders_arc import ArcRaidersArcConnector
from crawler_app.connectors.arc_raiders_weapons import ArcRaidersWeaponsConnector
from crawler_app.connectors.base import ConnectorError
from crawler_app.connectors.mihoyo_jobs import MihoyoJobsConnector
from crawler_app.models import ArcEnemyBundle, CrawlBundle, WeaponBundle
from crawler_app.storage import SQLiteStorage


class CrawlService:
    def __init__(self, storage: SQLiteStorage | None = None) -> None:
        self.storage = storage or SQLiteStorage()
        self.connectors = get_connectors()

    def crawl_source(
        self,
        source: str,
        target: str,
        related_limit: int = 10,
    ) -> tuple[CrawlBundle | WeaponBundle | ArcEnemyBundle, int]:
        started_at = datetime.now(timezone.utc).isoformat()
        connector = self.connectors[source]
        try:
            bundle = connector.crawl(target=target, related_limit=related_limit)
            if isinstance(bundle, CrawlBundle):
                run_id = self.storage.save_crawl_bundle(bundle)
                if source == "mihoyo_jobs":
                    self.refresh_job_ai_analysis(source)
            elif isinstance(bundle, WeaponBundle):
                run_id = self.storage.save_weapon_bundle(bundle)
            elif isinstance(bundle, ArcEnemyBundle):
                run_id = self.storage.save_arc_enemy_bundle(bundle)
            else:
                raise ConnectorError(f"未知的抓取结果类型: {type(bundle)!r}")
            return bundle, run_id
        except Exception as error:
            finished_at = datetime.now(timezone.utc).isoformat()
            message = str(error)
            self.storage.record_failed_run(
                source=source,
                target=target,
                started_at=started_at,
                finished_at=finished_at,
                error_message=message,
            )
            if isinstance(error, ConnectorError):
                raise
            raise ConnectorError(message) from error

    def sync_category_jobs(
        self,
        source: str,
        competency_type_id: str,
        internships_only: bool = True,
    ) -> tuple[int, int]:
        started_at = datetime.now(timezone.utc).isoformat()
        connector = self._get_mihoyo_connector(source)
        job_natures = [3] if internships_only else None
        jobs, raw_snapshot = connector.fetch_jobs_by_filters(
            competency_types=[competency_type_id],
            job_natures=job_natures,
        )
        finished_at = datetime.now(timezone.utc).isoformat()
        run_id = self.storage.save_job_batch(
            source=source,
            target=f"category:{competency_type_id}:internships_only={internships_only}",
            jobs=jobs,
            raw_snapshot=raw_snapshot,
            started_at=started_at,
            finished_at=finished_at,
        )
        self.refresh_job_ai_analysis(source)
        return len(jobs), run_id

    def sync_all_jobs(self, source: str, internships_only: bool = True) -> tuple[int, int]:
        started_at = datetime.now(timezone.utc).isoformat()
        connector = self._get_mihoyo_connector(source)
        job_natures = [3] if internships_only else None
        jobs, raw_snapshot = connector.fetch_jobs_by_filters(
            competency_types=None,
            job_natures=job_natures,
        )
        finished_at = datetime.now(timezone.utc).isoformat()
        run_id = self.storage.save_job_batch(
            source=source,
            target=f"all:internships_only={internships_only}",
            jobs=jobs,
            raw_snapshot=raw_snapshot,
            started_at=started_at,
            finished_at=finished_at,
        )
        self.refresh_job_ai_analysis(source)
        return len(jobs), run_id

    def fetch_category_counts(self, source: str, internships_only: bool = True) -> list[dict[str, object]]:
        connector = self._get_mihoyo_connector(source)
        return connector.fetch_category_counts(internships_only=internships_only)

    def refresh_job_ai_analysis(self, source: str) -> int:
        jobs_df = self.storage.jobs_dataframe(source)
        if jobs_df.empty:
            return 0

        analysis_df = build_ai_focus_dataframe(enrich_jobs_dataframe(jobs_df))
        if analysis_df.empty:
            return 0

        analyzed_at = datetime.now(timezone.utc).isoformat()
        return self.storage.save_job_ai_analysis(
            source=source,
            analyses=analysis_df.to_dict("records"),
            analyzed_at=analyzed_at,
        )

    def sync_arc_raiders_weapons(
        self,
        source: str,
        category_title: str = ARC_RAIDERS_WEAPON_CATEGORY,
        only_missing: bool = True,
    ) -> dict[str, object]:
        connector = self._get_arc_raiders_connector(source)
        discovered_titles = connector.fetch_weapon_titles(category_title=category_title)
        existing_df = self.storage.weapons_dataframe(source)
        existing_titles = set(existing_df["item_id"].tolist()) if not existing_df.empty else set()
        pending_titles = [
            title for title in discovered_titles
            if not only_missing or title not in existing_titles
        ]

        synced: list[dict[str, object]] = []
        failures: list[dict[str, str]] = []
        for title in pending_titles:
            try:
                _, run_id = self.crawl_source(source=source, target=title)
                synced.append({"title": title, "run_id": run_id})
            except ConnectorError as error:
                failures.append({"title": title, "error": str(error)})

        return {
            "category_title": category_title,
            "discovered_titles": discovered_titles,
            "existing_titles": sorted(existing_titles),
            "pending_titles": pending_titles,
            "skipped_titles": [title for title in discovered_titles if title not in pending_titles],
            "synced": synced,
            "failures": failures,
        }

    def sync_arc_raiders_arc(
        self,
        source: str,
        overview_page: str = ARC_RAIDERS_ARC_OVERVIEW_PAGE,
        only_missing: bool = True,
    ) -> dict[str, object]:
        connector = self._get_arc_raiders_arc_connector(source)
        discovered_titles = connector.fetch_enemy_titles(overview_page=overview_page)
        existing_df = self.storage.arc_enemies_dataframe(source)
        existing_titles = set(existing_df["item_id"].tolist()) if not existing_df.empty else set()
        pending_titles = [
            title for title in discovered_titles
            if not only_missing or title not in existing_titles
        ]

        synced: list[dict[str, object]] = []
        failures: list[dict[str, str]] = []
        for title in pending_titles:
            try:
                _, run_id = self.crawl_source(source=source, target=title)
                synced.append({"title": title, "run_id": run_id})
            except ConnectorError as error:
                failures.append({"title": title, "error": str(error)})

        return {
            "overview_page": overview_page,
            "discovered_titles": discovered_titles,
            "existing_titles": sorted(existing_titles),
            "pending_titles": pending_titles,
            "skipped_titles": [title for title in discovered_titles if title not in pending_titles],
            "synced": synced,
            "failures": failures,
        }

    def _get_mihoyo_connector(self, source: str) -> MihoyoJobsConnector:
        connector = self.connectors[source]
        if not isinstance(connector, MihoyoJobsConnector):
            raise ConnectorError(f"当前批量同步只支持 miHoYo 连接器: {source}")
        return connector

    def _get_arc_raiders_connector(self, source: str) -> ArcRaidersWeaponsConnector:
        connector = self.connectors[source]
        if not isinstance(connector, ArcRaidersWeaponsConnector):
            raise ConnectorError(f"当前批量同步只支持 ARC Raiders 武器连接器: {source}")
        return connector

    def _get_arc_raiders_arc_connector(self, source: str) -> ArcRaidersArcConnector:
        connector = self.connectors[source]
        if not isinstance(connector, ArcRaidersArcConnector):
            raise ConnectorError(f"当前批量同步只支持 ARC Raiders 怪物连接器: {source}")
        return connector
