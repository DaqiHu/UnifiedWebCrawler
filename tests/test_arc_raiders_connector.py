from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock

from crawler_app.connectors.arc_raiders_weapons import ArcRaidersWeaponsConnector


class ArcRaidersWeaponsConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connector = ArcRaidersWeaponsConnector()
        self.fixture_path = Path(__file__).resolve().parent.parent / "temp" / "target.html"
        self.html = self.fixture_path.read_text(encoding="utf-8")

    def test_resolve_page_title_supports_url_and_plain_title(self) -> None:
        self.assertEqual(
            self.connector.resolve_page_title("https://arcraiders.wiki/wiki/Kettle"),
            "Kettle",
        )
        self.assertEqual(self.connector.resolve_page_title("Kettle"), "Kettle")

    def test_fetch_weapon_titles_filters_category_entries(self) -> None:
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "query": {
                "categorymembers": [
                    {"title": "Kettle"},
                    {"title": "Anvil"},
                    {"title": "Category:Weapon types"},
                    {"title": "Kettle"},
                ]
            }
        }
        self.connector.client = Mock()
        self.connector.client.get.return_value = response

        titles = self.connector.fetch_weapon_titles()

        self.assertEqual(titles, ["Anvil", "Kettle"])

    def test_parse_weapon_page_extracts_infobox_and_resource_tables(self) -> None:
        weapon = self.connector.parse_weapon_page(
            html=self.html,
            page_title="Kettle",
            page_url="https://arcraiders.wiki/wiki/Kettle",
        )

        self.assertEqual(weapon.title, "Kettle")
        self.assertEqual(weapon.item_type, "Assault Rifle")
        self.assertEqual(weapon.rarity, "Common")
        self.assertEqual(weapon.ammo_type, "Light Ammo")
        self.assertEqual(weapon.firing_mode, "Semi-Automatic")
        self.assertEqual(weapon.arc_armor_penetration, "Very Weak")
        self.assertEqual(weapon.stats["Damage"], "8.5")
        self.assertEqual(weapon.mod_slots, ["Muzzle", "Underbarrel", "Light-Mag", "Stock"])
        self.assertEqual(weapon.sources, ["Scavenging", "Crafting", "Sold by Tian Wen"])
        self.assertEqual(weapon.crafting[0]["Result"], "1× Kettle I")
        self.assertEqual(weapon.upgrading[-1]["Result"], "Kettle IV")
        self.assertIn("40% Reduced Reload Time", weapon.upgrading[-1]["Perks"])
        self.assertEqual(weapon.repairing[0]["Item"], "Kettle I")
        self.assertEqual(weapon.recycling[-1]["Salvaging results"], "2× Simple Gun Parts")
        self.assertEqual(weapon.price_comparison[0]["Weapon Sale Price"], "840")
        self.assertIn("Reduced Base Damage from 10 to 8.5", weapon.history[0]["Changes"])


if __name__ == "__main__":
    unittest.main()
