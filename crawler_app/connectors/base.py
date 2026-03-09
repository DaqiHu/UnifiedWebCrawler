from __future__ import annotations

from abc import ABC, abstractmethod

from crawler_app.models import CrawlBundle


class ConnectorError(RuntimeError):
    """Raised when a connector cannot complete a crawl."""


class BaseConnector(ABC):
    source: str
    display_name: str
    data_kind: str
    description: str
    default_target: str

    @abstractmethod
    def crawl(self, target: str, related_limit: int = 10) -> CrawlBundle:
        raise NotImplementedError
