from __future__ import annotations

import argparse

from crawler_app.config import ARC_RAIDERS_WEAPON_CATEGORY
from crawler_app.service import CrawlService


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync ARC Raiders weapon pages from the wiki category.")
    parser.add_argument("--source", default="arc_raiders_weapons")
    parser.add_argument("--category", default=ARC_RAIDERS_WEAPON_CATEGORY)
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Re-crawl pages that already exist in the local database.",
    )
    args = parser.parse_args()

    service = CrawlService()
    result = service.sync_arc_raiders_weapons(
        source=args.source,
        category_title=args.category,
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
