from __future__ import annotations

from datetime import datetime, timezone

from crawler_app.connectors import get_connectors
from crawler_app.connectors.base import ConnectorError
from crawler_app.models import CrawlBundle
from crawler_app.storage import SQLiteStorage


class CrawlService:
    def __init__(self, storage: SQLiteStorage | None = None) -> None:
        self.storage = storage or SQLiteStorage()
        self.connectors = get_connectors()

    def crawl_source(self, source: str, target: str, related_limit: int = 10) -> tuple[CrawlBundle, int]:
        started_at = datetime.now(timezone.utc).isoformat()
        connector = self.connectors[source]
        try:
            bundle = connector.crawl(target=target, related_limit=related_limit)
            run_id = self.storage.save_crawl_bundle(bundle)
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
