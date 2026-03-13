from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from crawler_app.config import ARC_RAIDERS_DEFAULT_TARGET, ARC_RAIDERS_WIKI_API, HTTP_TIMEOUT_SECONDS
from crawler_app.connectors.base import BaseConnector, ConnectorError
from crawler_app.models import WeaponBundle, WeaponRecord


class ArcRaidersWeaponsConnector(BaseConnector):
    source = "arc_raiders_weapons"
    display_name = "ARC Raiders Wiki Weapons"
    data_kind = "武器资料"
    description = "抓取 ARC Raiders wiki 武器页的基础属性、来源和资源循环表。"
    default_target = ARC_RAIDERS_DEFAULT_TARGET

    def __init__(self) -> None:
        self.client = httpx.Client(
            timeout=HTTP_TIMEOUT_SECONDS,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
                ),
            },
        )

    def crawl(self, target: str, related_limit: int = 10) -> WeaponBundle:
        del related_limit
        started_at = datetime.now(timezone.utc).isoformat()
        page_title = self.resolve_page_title(target)
        payload = self._fetch_parse_payload(page_title)
        page_url = self._build_page_url(page_title)
        weapon = self.parse_weapon_page(payload["text"], payload["title"], page_url)
        finished_at = datetime.now(timezone.utc).isoformat()
        return WeaponBundle(
            source=self.source,
            target=target,
            primary_weapon=weapon,
            raw_snapshot={
                "page_title": page_title,
                "page_url": page_url,
                "parse_payload": payload,
            },
            started_at=started_at,
            finished_at=finished_at,
        )

    def resolve_page_title(self, target: str) -> str:
        value = target.strip()
        if not value:
            raise ConnectorError("目标不能为空。")
        if "arcraiders.wiki" in value:
            parsed = urlparse(value)
            if parsed.path.startswith("/wiki/"):
                title = parsed.path.removeprefix("/wiki/")
                title = unquote(title).replace("_", " ").strip()
                if title:
                    return title
        return unquote(value).replace("_", " ").strip()

    def parse_weapon_page(self, html: str, page_title: str, page_url: str) -> WeaponRecord:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".mw-parser-output") or soup
        infobox = root.select_one("table.infobox")
        if infobox is None:
            raise ConnectorError(f"页面 {page_title} 中未找到武器 infobox。")

        infobox_tags = self._dedupe(
            self._extract_text(anchor)
            for anchor in infobox.select("tr.data-tag.link-button a")
        )
        stats = self._parse_infobox_stats(infobox)
        sections = self._parse_sections(root)
        lead_paragraphs = self._extract_lead_paragraphs(root)

        return WeaponRecord(
            source=self.source,
            item_id=page_title,
            url=page_url,
            title=self._first_non_empty(
                self._extract_text(infobox.select_one("tr.infobox-title")),
                page_title,
            ),
            item_type=infobox_tags[0] if infobox_tags else "",
            rarity=infobox_tags[1] if len(infobox_tags) > 1 else "",
            ammo_type=stats.get("Ammo Type", ""),
            firing_mode=stats.get("Firing Mode", ""),
            arc_armor_penetration=stats.get("ARC Armor Penetration", ""),
            magazine_size=stats.get("Magazine Size", ""),
            quote=self._extract_text(infobox.select_one("tr.data-weaponquote")),
            summary="\n\n".join(lead_paragraphs),
            infobox_tags=infobox_tags,
            mod_slots=self._parse_mod_slots(infobox),
            stats=stats,
            sources=sections.get("Sources", {}).get("list", []),
            crafting=sections.get("Crafting", {}).get("table", []),
            upgrading=sections.get("Upgrading", {}).get("table", []),
            repairing=sections.get("Repairing", {}).get("table", []),
            recycling=sections.get("Recycling & Salvaging", {}).get("table", []),
            price_comparison=sections.get(
                "Weapon Sale Price vs Component Sale Price Per Inventory Slot",
                {},
            ).get("table", []),
            history=sections.get("History", {}).get("table", []),
            raw_payload={
                "page_title": page_title,
                "html": html,
                "lead_paragraphs": lead_paragraphs,
                "sections": sections,
                "stats": stats,
            },
        )

    def _fetch_parse_payload(self, page_title: str) -> dict[str, Any]:
        response = self.client.get(
            ARC_RAIDERS_WIKI_API,
            params={
                "action": "parse",
                "page": page_title,
                "prop": "text",
                "format": "json",
                "formatversion": "2",
            },
        )
        response.raise_for_status()
        body = response.json()
        if "error" in body:
            raise ConnectorError(f"wiki parse API 失败: {body['error'].get('info', body['error'])}")
        return body["parse"]

    def _build_page_url(self, page_title: str) -> str:
        return f"https://arcraiders.wiki/wiki/{page_title.replace(' ', '_')}"

    def _parse_infobox_stats(self, infobox: Tag) -> dict[str, str]:
        stats: dict[str, str] = {}
        for row in infobox.select("tr.infobox-data"):
            header = self._extract_text(row.find("th", recursive=False))
            value = self._extract_text(row.find("td", recursive=False))
            if header:
                stats[header] = value
        return stats

    def _parse_mod_slots(self, infobox: Tag) -> list[str]:
        slots: list[str] = []
        for node in infobox.select("tr.data-mods span[title], tr.data-mods img[alt]"):
            label = ""
            if node.has_attr("title"):
                label = str(node["title"]).strip()
            elif node.has_attr("alt"):
                label = str(node["alt"]).strip()
            if label and label not in slots:
                slots.append(label)
        return slots

    def _parse_sections(self, root: Tag) -> dict[str, dict[str, Any]]:
        sections: dict[str, dict[str, Any]] = {}
        for heading_wrapper in root.select("div.mw-heading"):
            heading = heading_wrapper.find("h2")
            if heading is None:
                continue
            section_name = self._extract_text(heading)
            nodes = self._collect_section_nodes(heading_wrapper)
            list_items = self._dedupe(
                self._extract_text(item)
                for node in nodes
                for item in node.select("ul > li")
            )
            table = []
            for node in nodes:
                candidate = node if node.name == "table" else node.select_one("table")
                if candidate is not None:
                    table = self._parse_table(candidate)
                    break
            sections[section_name] = {
                "list": list_items,
                "table": table,
                "text": "\n\n".join(text for text in (self._extract_text(node) for node in nodes) if text),
            }
        return sections

    def _collect_section_nodes(self, heading_wrapper: Tag) -> list[Tag]:
        nodes: list[Tag] = []
        sibling = heading_wrapper.find_next_sibling()
        while isinstance(sibling, Tag):
            if sibling.name == "div" and "mw-heading" in sibling.get("class", []):
                break
            nodes.append(sibling)
            sibling = sibling.find_next_sibling()
        return nodes

    def _extract_lead_paragraphs(self, root: Tag) -> list[str]:
        paragraphs: list[str] = []
        for child in root.children:
            if not isinstance(child, Tag):
                continue
            if child.name == "div" and "mw-heading" in child.get("class", []):
                break
            if child.name == "p":
                text = self._extract_text(child)
                if text:
                    paragraphs.append(text)
        return paragraphs

    def _parse_table(self, table: Tag) -> list[dict[str, str]]:
        rows = table.select("tr")
        if not rows:
            return []
        headers = [self._extract_text(cell) for cell in rows[0].find_all(["th", "td"], recursive=False)]
        if not any(headers):
            return []

        records: list[dict[str, str]] = []
        for row in rows[1:]:
            cells = row.find_all(["th", "td"], recursive=False)
            if not cells:
                continue
            values = [self._extract_text(cell) for cell in cells]
            if not any(values):
                continue
            normalized_headers = list(headers)
            if len(values) > len(normalized_headers):
                normalized_headers.extend(
                    f"column_{index}"
                    for index in range(len(normalized_headers) + 1, len(values) + 1)
                )
            if len(values) < len(normalized_headers):
                values.extend([""] * (len(normalized_headers) - len(values)))
            records.append(
                {normalized_headers[index]: values[index] for index in range(len(normalized_headers))}
            )
        return records

    def _extract_text(self, node: Tag | None) -> str:
        if node is None:
            return ""
        clone = BeautifulSoup(str(node), "html.parser")
        for line_break in clone.find_all("br"):
            line_break.replace_with("\n")
        text = clone.get_text(" ", strip=True)
        lines = []
        for raw_line in text.splitlines():
            line = " ".join(raw_line.split())
            if line:
                lines.append(line)
        return "\n".join(lines)

    def _dedupe(self, values: Any) -> list[str]:
        seen: list[str] = []
        for value in values:
            if value and value not in seen:
                seen.append(value)
        return seen

    def _first_non_empty(self, *values: str) -> str:
        for value in values:
            if value:
                return value
        return ""
