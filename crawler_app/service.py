from __future__ import annotations

from datetime import datetime, timezone

from crawler_app.connectors import get_connectors
from crawler_app.connectors.base import ConnectorError
from crawler_app.connectors.mihoyo_jobs import MihoyoJobsConnector
from crawler_app.models import CrawlBundle, WeaponBundle
from crawler_app.storage import SQLiteStorage


class CrawlService:
    def __init__(self, storage: SQLiteStorage | None = None) -> None:
        self.storage = storage or SQLiteStorage()
        self.connectors = get_connectors()

    def crawl_source(self, source: str, target: str, related_limit: int = 10) -> tuple[CrawlBundle | WeaponBundle, int]:
        started_at = datetime.now(timezone.utc).isoformat()
        connector = self.connectors[source]
        try:
            bundle = connector.crawl(target=target, related_limit=related_limit)
            if isinstance(bundle, CrawlBundle):
                run_id = self.storage.save_crawl_bundle(bundle)
            elif isinstance(bundle, WeaponBundle):
                run_id = self.storage.save_weapon_bundle(bundle)
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
        return len(jobs), run_id

    def fetch_category_counts(self, source: str, internships_only: bool = True) -> list[dict[str, object]]:
        connector = self._get_mihoyo_connector(source)
        return connector.fetch_category_counts(internships_only=internships_only)

    def _get_mihoyo_connector(self, source: str) -> MihoyoJobsConnector:
        connector = self.connectors[source]
        if not isinstance(connector, MihoyoJobsConnector):
            raise ConnectorError(f"当前批量同步只支持 miHoYo 连接器: {source}")
        return connector
