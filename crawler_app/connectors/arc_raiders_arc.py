from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from crawler_app.config import (
    ARC_RAIDERS_ARC_DEFAULT_TARGET,
    ARC_RAIDERS_ARC_OVERVIEW_PAGE,
    ARC_RAIDERS_WIKI_API,
    HTTP_TIMEOUT_SECONDS,
)
from crawler_app.connectors.base import BaseConnector, ConnectorError
from crawler_app.models import ArcEnemyBundle, ArcEnemyRecord


class ArcRaidersArcConnector(BaseConnector):
    source = "arc_raiders_arc"
    display_name = "ARC Raiders ARC Enemies"
    data_kind = "怪物资料"
    description = "抓取 ARC Raiders wiki 中 ARC 敌人页的基础属性、战斗提示、掉落和图鉴条目。"
    default_target = ARC_RAIDERS_ARC_DEFAULT_TARGET

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

    def crawl(self, target: str, related_limit: int = 10) -> ArcEnemyBundle:
        del related_limit
        started_at = datetime.now(timezone.utc).isoformat()
        page_title = self.resolve_page_title(target)
        payload = self._fetch_parse_payload(page_title)
        page_url = self._build_page_url(payload["title"])
        enemy = self.parse_enemy_page(payload["text"], payload["title"], page_url)
        finished_at = datetime.now(timezone.utc).isoformat()
        return ArcEnemyBundle(
            source=self.source,
            target=target,
            primary_enemy=enemy,
            raw_snapshot={
                "page_title": page_title,
                "page_url": page_url,
                "parse_payload": payload,
            },
            started_at=started_at,
            finished_at=finished_at,
        )

    def fetch_enemy_titles(self, overview_page: str = ARC_RAIDERS_ARC_OVERVIEW_PAGE) -> list[str]:
        payload = self._fetch_parse_payload(overview_page)
        soup = BeautifulSoup(payload["text"], "html.parser")
        root = soup.select_one(".mw-parser-output") or soup
        titles = self._extract_titles_from_sections(root, section_names=("Variants",))
        if not titles:
            raise ConnectorError(f"页面 {overview_page} 中未找到 ARC 敌人标题列表。")
        return titles

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

    def parse_enemy_page(self, html: str, page_title: str, page_url: str) -> ArcEnemyRecord:
        soup = BeautifulSoup(html, "html.parser")
        root = soup.select_one(".mw-parser-output") or soup
        infobox = root.select_one("table.infobox")
        if infobox is None:
            raise ConnectorError(f"页面 {page_title} 中未找到 ARC 怪物 infobox。")

        stats = self._parse_infobox_stats(infobox)
        if not stats.get("Threat Level"):
            raise ConnectorError(f"页面 {page_title} 不是可解析的 ARC 敌人页。")

        sections = self._parse_sections(root)
        lead_paragraphs = self._extract_lead_paragraphs(root)

        return ArcEnemyRecord(
            source=self.source,
            item_id=page_title,
            url=page_url,
            title=self._first_non_empty(
                self._extract_text(infobox.select_one("tr.infobox-title")),
                page_title,
            ),
            threat_level=stats.get("Threat Level", ""),
            armor=stats.get("Armor", ""),
            primary_attack=stats.get("Primary Attack", ""),
            weakness=stats.get("Weakness", ""),
            abilities=stats.get("Abilities", ""),
            xp_gained=stats.get("XP Gained", ""),
            health=stats.get("Health", ""),
            summary="\n\n".join(lead_paragraphs),
            stats=stats,
            attack_text=sections.get("Attack", {}).get("text", ""),
            behavior_text=sections.get("Behavior", {}).get("text", ""),
            abilities_text=sections.get("Abilities", {}).get("text", ""),
            codex_entry=sections.get("Codex entry", {}).get("text", ""),
            combat_tips=sections.get("Combat tips", {}).get("list", []),
            loot=self._resolve_loot_rows(sections.get("Loot", {})),
            locations=sections.get("Locations", {}).get("list", []),
            history=sections.get("History", {}).get("table", []),
            changelog=sections.get("Changelog", {}).get("table", []),
            trivia=sections.get("Trivia", {}).get("list", []),
            achievement_tips=sections.get("Achievement tips", {}).get("list", []),
            references=sections.get("References", {}).get("list", []),
            sections=sections,
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

    def _extract_titles_from_sections(self, root: Tag, section_names: tuple[str, ...]) -> list[str]:
        titles: list[str] = []
        allowed_sections = set(section_names)
        for heading_wrapper in root.select("div.mw-heading"):
            heading = heading_wrapper.find("h2")
            if heading is None:
                continue
            section_name = self._extract_text(heading)
            if section_name not in allowed_sections:
                continue
            for node in self._collect_section_nodes(heading_wrapper):
                if node.name != "table":
                    continue
                for row in node.select("tr")[1:]:
                    first_cell = row.find(["th", "td"], recursive=False)
                    if first_cell is None:
                        continue
                    anchor = first_cell.select_one("a[href^='/wiki/']")
                    if anchor is None:
                        continue
                    href = str(anchor.get("href", "")).strip()
                    title = unquote(href.removeprefix("/wiki/")).replace("_", " ").strip()
                    if title and title not in titles:
                        titles.append(title)
        return titles

    def _parse_infobox_stats(self, infobox: Tag) -> dict[str, str]:
        stats: dict[str, str] = {}
        for row in infobox.select("tr.infobox-data"):
            header = self._extract_text(row.find("th", recursive=False))
            value = self._extract_text(row.find("td", recursive=False))
            if header:
                stats[header] = value
        return stats

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
            table: list[dict[str, str]] = []
            for node in nodes:
                candidate = node if node.name == "table" else node.select_one("table")
                if candidate is not None:
                    table = self._parse_table(candidate)
                    break
            item_grid = self._dedupe(
                self._extract_text(item)
                for node in nodes
                for item in node.select(".item-grid .item-name")
            )
            sections[section_name] = {
                "list": list_items,
                "table": table,
                "item_grid": item_grid,
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

    def _resolve_loot_rows(self, loot_section: dict[str, Any]) -> list[dict[str, str]]:
        table_rows = loot_section.get("table", [])
        if table_rows:
            return table_rows

        item_grid = loot_section.get("item_grid", [])
        if item_grid:
            return [{"Item": item_name} for item_name in item_grid]

        list_items = loot_section.get("list", [])
        if list_items:
            return [{"Item": item_name} for item_name in list_items]

        return []
