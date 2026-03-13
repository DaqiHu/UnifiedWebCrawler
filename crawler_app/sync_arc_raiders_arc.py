from __future__ import annotations

import argparse

from crawler_app.config import ARC_RAIDERS_ARC_OVERVIEW_PAGE
from crawler_app.service import CrawlService


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync ARC Raiders ARC enemy pages from the overview page.")
    parser.add_argument("--source", default="arc_raiders_arc")
    parser.add_argument("--overview-page", default=ARC_RAIDERS_ARC_OVERVIEW_PAGE)
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Re-crawl pages that already exist in the local database.",
    )
    args = parser.parse_args()

    service = CrawlService()
    result = service.sync_arc_raiders_arc(
        source=args.source,
        overview_page=args.overview_page,
        only_missing=not args.include_existing,
    )

    print(
        "Discovered "
        f"{len(result['discovered_titles'])} pages; "
        f"synced {len(result['synced'])}; "
        f"skipped {len(result['skipped_titles'])}; "
        f"failed {len(result['failures'])}."
    )
    for item in result["synced"]:
        print(f"[OK] {item['title']} -> run #{item['run_id']}")
    for item in result["failures"]:
        print(f"[FAIL] {item['title']} -> {item['error']}")


if __name__ == "__main__":
    main()
