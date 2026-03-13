from __future__ import annotations

import argparse

from crawler_app.config import DEFAULT_SOURCE, DEFAULT_TARGET
from crawler_app.models import ArcEnemyBundle, CrawlBundle, WeaponBundle
from crawler_app.service import CrawlService


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed crawler data for the Streamlit app.")
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--related-limit", default=10, type=int)
    args = parser.parse_args()

    service = CrawlService()
    bundle, run_id = service.crawl_source(
        source=args.source,
        target=args.target,
        related_limit=args.related_limit,
    )
    if isinstance(bundle, CrawlBundle):
        print(
            f"Saved crawl run #{run_id}: {bundle.primary_job.title} "
            f"+ {len(bundle.related_jobs)} related jobs"
        )
        return
    if isinstance(bundle, WeaponBundle):
        print(f"Saved crawl run #{run_id}: {bundle.primary_weapon.title}")
        return
    if isinstance(bundle, ArcEnemyBundle):
        print(f"Saved crawl run #{run_id}: {bundle.primary_enemy.title}")
        return
    raise RuntimeError(f"Unsupported bundle type: {type(bundle)!r}")


if __name__ == "__main__":
    main()
