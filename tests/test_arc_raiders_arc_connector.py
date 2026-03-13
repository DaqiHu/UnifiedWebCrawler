from __future__ import annotations

import unittest
from unittest.mock import Mock

from crawler_app.connectors.arc_raiders_arc import ArcRaidersArcConnector


OVERVIEW_HTML = """
<div class="mw-parser-output">
  <div class="mw-heading"><h2>Variants</h2></div>
  <table class="wikitable">
    <tr><th>ARC</th><th>Drops</th></tr>
    <tr><td><a href="/wiki/Snitch">Snitch</a></td><td>Scanner</td></tr>
    <tr><td><a href="/wiki/ARC_Surveyor">Surveyor</a></td><td>Vault</td></tr>
  </table>
</div>
"""

SNITCH_HTML = """
<div class="mw-parser-output">
  <p>The Snitch is a flying ARC scout.</p>
  <table class="infobox">
    <tr class="infobox-title"><th>Snitch</th></tr>
    <tr class="infobox-data"><th>Threat Level</th><td>Moderate</td></tr>
    <tr class="infobox-data"><th>Armor</th><td>None</td></tr>
    <tr class="infobox-data"><th>Primary Attack</th><td>None</td></tr>
    <tr class="infobox-data"><th>Abilities</th><td>Summon ARC</td></tr>
    <tr class="infobox-data"><th>Weakness</th><td>Thrusters</td></tr>
    <tr class="infobox-data"><th>XP Gained</th><td>Destroy: +100 XP</td></tr>
    <tr class="infobox-data"><th>Health</th><td>158</td></tr>
  </table>
  <div class="mw-heading"><h2>Combat tips</h2></div>
  <ul><li>Destroy it quickly.</li><li>Aim for the thrusters.</li></ul>
  <div class="mw-heading"><h2>Loot</h2></div>
  <table class="wikitable">
    <tr><th>Item</th><th>Chance</th></tr>
    <tr><td>Snitch Scanner</td><td>100%</td></tr>
  </table>
  <div class="mw-heading"><h2>Codex entry</h2></div>
  <p>ARC scouts that call reinforcements.</p>
</div>
"""

SNITCH_ITEM_GRID_HTML = """
<div class="mw-parser-output">
  <table class="infobox">
    <tr class="infobox-title"><th>Snitch</th></tr>
    <tr class="infobox-data"><th>Threat Level</th><td>Moderate</td></tr>
  </table>
  <div class="mw-heading"><h2>Loot</h2></div>
  <div class="item-grid">
    <div class="item-cell"><div class="item-name">ARC Powercell</div></div>
    <div class="item-cell"><div class="item-name">Snitch Scanner</div></div>
  </div>
</div>
"""


class ArcRaidersArcConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = ArcRaidersArcConnector()

    def test_resolve_page_title_supports_url_and_plain_title(self) -> None:
        self.assertEqual(
            self.connector.resolve_page_title("https://arcraiders.wiki/wiki/Snitch"),
            "Snitch",
        )
        self.assertEqual(self.connector.resolve_page_title("ARC_Surveyor"), "ARC Surveyor")

    def test_fetch_enemy_titles_uses_variants_table_links(self) -> None:
        self.connector._fetch_parse_payload = Mock(return_value={"title": "ARC", "text": OVERVIEW_HTML})

        titles = self.connector.fetch_enemy_titles()

        self.assertEqual(titles, ["Snitch", "ARC Surveyor"])

    def test_parse_enemy_page_extracts_core_sections(self) -> None:
        enemy = self.connector.parse_enemy_page(
            html=SNITCH_HTML,
            page_title="Snitch",
            page_url="https://arcraiders.wiki/wiki/Snitch",
        )

        self.assertEqual(enemy.title, "Snitch")
        self.assertEqual(enemy.threat_level, "Moderate")
        self.assertEqual(enemy.armor, "None")
        self.assertEqual(enemy.primary_attack, "None")
        self.assertEqual(enemy.abilities, "Summon ARC")
        self.assertEqual(enemy.weakness, "Thrusters")
        self.assertEqual(enemy.health, "158")
        self.assertIn("flying ARC scout", enemy.summary)
        self.assertEqual(enemy.combat_tips, ["Destroy it quickly.", "Aim for the thrusters."])
        self.assertEqual(enemy.loot[0]["Item"], "Snitch Scanner")
        self.assertIn("call reinforcements", enemy.codex_entry)

    def test_parse_enemy_page_supports_item_grid_loot(self) -> None:
        enemy = self.connector.parse_enemy_page(
            html=SNITCH_ITEM_GRID_HTML,
            page_title="Snitch",
            page_url="https://arcraiders.wiki/wiki/Snitch",
        )

        self.assertEqual(enemy.loot, [{"Item": "ARC Powercell"}, {"Item": "Snitch Scanner"}])


if __name__ == "__main__":
    unittest.main()
