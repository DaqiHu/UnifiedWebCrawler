from __future__ import annotations

from crawler_app.connectors.mihoyo_jobs import MihoyoJobsConnector


def get_connectors() -> dict[str, MihoyoJobsConnector]:
    connector = MihoyoJobsConnector()
    return {connector.source: connector}
