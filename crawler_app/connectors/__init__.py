from __future__ import annotations

from crawler_app.connectors.arc_raiders_weapons import ArcRaidersWeaponsConnector
from crawler_app.connectors.base import BaseConnector
from crawler_app.connectors.mihoyo_jobs import MihoyoJobsConnector


def get_connectors() -> dict[str, BaseConnector]:
    connectors = [
        MihoyoJobsConnector(),
        ArcRaidersWeaponsConnector(),
    ]
    return {connector.source: connector for connector in connectors}
