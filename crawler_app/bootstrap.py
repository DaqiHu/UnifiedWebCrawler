from __future__ import annotations

import argparse

from crawler_app.config import DEFAULT_SOURCE, DEFAULT_TARGET
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
    print(
        f"Saved crawl run #{run_id}: {bundle.primary_job.title} "
        f"+ {len(bundle.related_jobs)} related jobs"
    )


if __name__ == "__main__":
    main()
