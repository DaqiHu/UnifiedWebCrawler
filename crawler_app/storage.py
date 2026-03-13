from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from crawler_app.config import DB_PATH, RAW_DIR, ensure_directories
from crawler_app.models import (
    ArcEnemyBundle,
    ArcEnemyRecord,
    CrawlBundle,
    JobRecord,
    WeaponBundle,
    WeaponRecord,
)


class SQLiteStorage:
    def __init__(self, db_path: Path = DB_PATH) -> None:
        ensure_directories()
        self.db_path = db_path
        self.init_db()

    def init_db(self) -> None:
        with sqlite3.connect(self.db_path) as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    source TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    location TEXT,
                    category TEXT,
                    category_id TEXT,
                    target_audience TEXT,
                    job_nature TEXT,
                    job_nature_id INTEGER,
                    hire_type_name TEXT,
                    hire_type_id INTEGER,
                    project_name TEXT,
                    description TEXT,
                    requirements TEXT,
                    bonus_points TEXT,
                    summary TEXT,
                    delivery_instructions TEXT,
                    address_ids_json TEXT NOT NULL,
                    channel_detail_ids_json TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    raw_payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source, job_id)
                );

                CREATE TABLE IF NOT EXISTS related_jobs (
                    source TEXT NOT NULL,
                    source_job_id TEXT NOT NULL,
                    related_job_id TEXT NOT NULL,
                    rank_order INTEGER NOT NULL,
                    related_title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (source, source_job_id, related_job_id)
                );

                CREATE TABLE IF NOT EXISTS crawl_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    primary_job_id TEXT NOT NULL,
                    job_count INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    raw_snapshot_path TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS weapon_pages (
                    source TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    item_type TEXT,
                    rarity TEXT,
                    ammo_type TEXT,
                    firing_mode TEXT,
                    arc_armor_penetration TEXT,
                    magazine_size TEXT,
                    quote TEXT,
                    summary TEXT,
                    infobox_tags_json TEXT NOT NULL,
                    mod_slots_json TEXT NOT NULL,
                    stats_json TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    crafting_json TEXT NOT NULL,
                    upgrading_json TEXT NOT NULL,
                    repairing_json TEXT NOT NULL,
                    recycling_json TEXT NOT NULL,
                    price_comparison_json TEXT NOT NULL,
                    history_json TEXT NOT NULL,
                    raw_payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source, item_id)
                );

                CREATE TABLE IF NOT EXISTS arc_enemy_pages (
                    source TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    threat_level TEXT,
                    armor TEXT,
                    primary_attack TEXT,
                    weakness TEXT,
                    abilities TEXT,
                    xp_gained TEXT,
                    health TEXT,
                    summary TEXT,
                    attack_text TEXT,
                    behavior_text TEXT,
                    abilities_text TEXT,
                    codex_entry TEXT,
                    stats_json TEXT NOT NULL,
                    combat_tips_json TEXT NOT NULL,
                    loot_json TEXT NOT NULL,
                    locations_json TEXT NOT NULL,
                    history_json TEXT NOT NULL,
                    changelog_json TEXT NOT NULL,
                    trivia_json TEXT NOT NULL,
                    achievement_tips_json TEXT NOT NULL,
                    references_json TEXT NOT NULL,
                    sections_json TEXT NOT NULL,
                    raw_payload_json TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (source, item_id)
                );
                """
            )
            self._ensure_job_columns(connection)

    def save_crawl_bundle(self, bundle: CrawlBundle) -> int:
        raw_snapshot_path = self._write_raw_snapshot(bundle)
        jobs = [bundle.primary_job, *bundle.related_jobs]

        with sqlite3.connect(self.db_path) as connection:
            for job in jobs:
                self._upsert_job(connection, job)

            connection.execute(
                "DELETE FROM related_jobs WHERE source = ? AND source_job_id = ?",
                (bundle.source, bundle.primary_job.job_id),
            )
            for link in bundle.related_links:
                connection.execute(
                    """
                    INSERT INTO related_jobs (
                        source, source_job_id, related_job_id, rank_order, related_title, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        bundle.source,
                        link.source_job_id,
                        link.related_job_id,
                        link.rank_order,
                        link.related_title,
                        bundle.finished_at,
                    ),
                )

            cursor = connection.execute(
                """
                INSERT INTO crawl_runs (
                    source, target, primary_job_id, job_count, status, raw_snapshot_path,
                    started_at, finished_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle.source,
                    bundle.target,
                    bundle.primary_job.job_id,
                    len(jobs),
                    "success",
                    str(raw_snapshot_path),
                    bundle.started_at,
                    bundle.finished_at,
                    None,
                ),
            )
            return int(cursor.lastrowid)

    def save_weapon_bundle(self, bundle: WeaponBundle) -> int:
        raw_snapshot_path = self._write_batch_snapshot(
            source=bundle.source,
            prefix=bundle.primary_weapon.item_id,
            raw_snapshot=bundle.raw_snapshot,
            finished_at=bundle.finished_at,
        )
        with sqlite3.connect(self.db_path) as connection:
            self._upsert_weapon(connection, bundle.primary_weapon)
            cursor = connection.execute(
                """
                INSERT INTO crawl_runs (
                    source, target, primary_job_id, job_count, status, raw_snapshot_path,
                    started_at, finished_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle.source,
                    bundle.target,
                    bundle.primary_weapon.item_id,
                    1,
                    "success",
                    str(raw_snapshot_path),
                    bundle.started_at,
                    bundle.finished_at,
                    None,
                ),
            )
            return int(cursor.lastrowid)

    def save_arc_enemy_bundle(self, bundle: ArcEnemyBundle) -> int:
        raw_snapshot_path = self._write_batch_snapshot(
            source=bundle.source,
            prefix=bundle.primary_enemy.item_id,
            raw_snapshot=bundle.raw_snapshot,
            finished_at=bundle.finished_at,
        )
        with sqlite3.connect(self.db_path) as connection:
            self._upsert_arc_enemy(connection, bundle.primary_enemy)
            cursor = connection.execute(
                """
                INSERT INTO crawl_runs (
                    source, target, primary_job_id, job_count, status, raw_snapshot_path,
                    started_at, finished_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle.source,
                    bundle.target,
                    bundle.primary_enemy.item_id,
                    1,
                    "success",
                    str(raw_snapshot_path),
                    bundle.started_at,
                    bundle.finished_at,
                    None,
                ),
            )
            return int(cursor.lastrowid)

    def save_job_batch(
        self,
        source: str,
        target: str,
        jobs: list[JobRecord],
        raw_snapshot: dict[str, Any],
        started_at: str,
        finished_at: str,
        primary_job_id: str = "",
    ) -> int:
        raw_snapshot_path = self._write_batch_snapshot(source, primary_job_id or "batch", raw_snapshot, finished_at)
        with sqlite3.connect(self.db_path) as connection:
            for job in jobs:
                self._upsert_job(connection, job)

            cursor = connection.execute(
                """
                INSERT INTO crawl_runs (
                    source, target, primary_job_id, job_count, status, raw_snapshot_path,
                    started_at, finished_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    target,
                    primary_job_id,
                    len(jobs),
                    "success",
                    str(raw_snapshot_path),
                    started_at,
                    finished_at,
                    None,
                ),
            )
            return int(cursor.lastrowid)

    def record_failed_run(
        self,
        source: str,
        target: str,
        started_at: str,
        finished_at: str,
        error_message: str,
    ) -> int:
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO crawl_runs (
                    source, target, primary_job_id, job_count, status, raw_snapshot_path,
                    started_at, finished_at, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source,
                    target,
                    "",
                    0,
                    "failed",
                    "",
                    started_at,
                    finished_at,
                    error_message,
                ),
            )
            return int(cursor.lastrowid)

    def jobs_dataframe(self, source: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM jobs"
        params: tuple[Any, ...] = ()
        if source:
            query += " WHERE source = ?"
            params = (source,)
        query += " ORDER BY updated_at DESC, title ASC"
        with sqlite3.connect(self.db_path) as connection:
            dataframe = pd.read_sql_query(query, connection, params=params)
        if dataframe.empty:
            return dataframe

        for column in (
            "address_ids_json",
            "channel_detail_ids_json",
            "tags_json",
            "raw_payload_json",
            "ai_focus_signals_json",
        ):
            if column in dataframe.columns:
                dataframe[column] = dataframe[column].map(self._load_json_or_default)
        return dataframe

    def save_job_ai_analysis(
        self,
        source: str,
        analyses: list[dict[str, Any]],
        analyzed_at: str | None = None,
    ) -> int:
        if not analyses:
            return 0

        timestamp = analyzed_at or datetime.now(timezone.utc).isoformat()
        updated_rows = 0
        with sqlite3.connect(self.db_path) as connection:
            for item in analyses:
                cursor = connection.execute(
                    """
                    UPDATE jobs
                    SET
                        ai_analysis = ?,
                        ai_focus_score = ?,
                        ai_focus_level = ?,
                        ai_focus_lane = ?,
                        ai_focus_reason = ?,
                        ai_focus_signals_json = ?,
                        ai_focus_updated_at = ?
                    WHERE source = ? AND job_id = ?
                    """,
                    (
                        str(item.get("ai_analysis", "") or ""),
                        int(item.get("ai_focus_score", 0) or 0),
                        str(item.get("ai_focus_level", "") or ""),
                        str(item.get("ai_focus_lane", "") or ""),
                        str(item.get("ai_focus_reason", "") or ""),
                        json.dumps(item.get("ai_focus_signals_json", []), ensure_ascii=False),
                        str(item.get("ai_focus_updated_at", "") or timestamp),
                        source,
                        str(item["job_id"]),
                    ),
                )
                updated_rows += int(cursor.rowcount or 0)
        return updated_rows

    def related_jobs_dataframe(self, source: str, source_job_id: str) -> pd.DataFrame:
        query = """
            SELECT
                r.rank_order,
                j.job_id,
                j.title,
                j.location,
                j.category,
                j.target_audience,
                j.job_nature,
                j.updated_at
            FROM related_jobs AS r
            JOIN jobs AS j
                ON j.source = r.source
               AND j.job_id = r.related_job_id
            WHERE r.source = ? AND r.source_job_id = ?
            ORDER BY r.rank_order ASC
        """
        with sqlite3.connect(self.db_path) as connection:
            return pd.read_sql_query(query, connection, params=(source, source_job_id))

    def weapons_dataframe(self, source: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM weapon_pages"
        params: tuple[Any, ...] = ()
        if source:
            query += " WHERE source = ?"
            params = (source,)
        query += " ORDER BY updated_at DESC, title ASC"
        with sqlite3.connect(self.db_path) as connection:
            dataframe = pd.read_sql_query(query, connection, params=params)
        if dataframe.empty:
            return dataframe

        for column in (
            "infobox_tags_json",
            "mod_slots_json",
            "stats_json",
            "sources_json",
            "crafting_json",
            "upgrading_json",
            "repairing_json",
            "recycling_json",
            "price_comparison_json",
            "history_json",
            "raw_payload_json",
        ):
            dataframe[column] = dataframe[column].map(json.loads)
        return dataframe

    def crawl_runs_dataframe(self, source: str | None = None, limit: int = 20) -> pd.DataFrame:
        query = "SELECT * FROM crawl_runs"
        params: tuple[Any, ...] = ()
        if source:
            query += " WHERE source = ?"
            params = (source,)
        query += " ORDER BY id DESC LIMIT ?"
        params = (*params, limit)
        with sqlite3.connect(self.db_path) as connection:
            return pd.read_sql_query(query, connection, params=params)

    def has_jobs(self, source: str) -> bool:
        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM jobs WHERE source = ?",
                (source,),
            ).fetchone()
        return bool(row and row[0])

    def has_weapons(self, source: str) -> bool:
        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM weapon_pages WHERE source = ?",
                (source,),
            ).fetchone()
        return bool(row and row[0])

    def arc_enemies_dataframe(self, source: str | None = None) -> pd.DataFrame:
        query = "SELECT * FROM arc_enemy_pages"
        params: tuple[Any, ...] = ()
        if source:
            query += " WHERE source = ?"
            params = (source,)
        query += " ORDER BY updated_at DESC, title ASC"
        with sqlite3.connect(self.db_path) as connection:
            dataframe = pd.read_sql_query(query, connection, params=params)
        if dataframe.empty:
            return dataframe

        for column in (
            "stats_json",
            "combat_tips_json",
            "loot_json",
            "locations_json",
            "history_json",
            "changelog_json",
            "trivia_json",
            "achievement_tips_json",
            "references_json",
            "sections_json",
            "raw_payload_json",
        ):
            dataframe[column] = dataframe[column].map(json.loads)
        return dataframe

    def has_arc_enemies(self, source: str) -> bool:
        with closing(sqlite3.connect(self.db_path)) as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM arc_enemy_pages WHERE source = ?",
                (source,),
            ).fetchone()
        return bool(row and row[0])

    def _upsert_job(self, connection: sqlite3.Connection, job: JobRecord) -> None:
        connection.execute(
            """
            INSERT INTO jobs (
                source, job_id, url, title, location, category, category_id, target_audience,
                job_nature, job_nature_id, hire_type_name, hire_type_id, project_name,
                description, requirements, bonus_points, summary, delivery_instructions,
                address_ids_json, channel_detail_ids_json, tags_json, raw_payload_json, fetched_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, job_id) DO UPDATE SET
                url = excluded.url,
                title = excluded.title,
                location = excluded.location,
                category = excluded.category,
                category_id = excluded.category_id,
                target_audience = excluded.target_audience,
                job_nature = excluded.job_nature,
                job_nature_id = excluded.job_nature_id,
                hire_type_name = excluded.hire_type_name,
                hire_type_id = excluded.hire_type_id,
                project_name = excluded.project_name,
                description = excluded.description,
                requirements = excluded.requirements,
                bonus_points = excluded.bonus_points,
                summary = excluded.summary,
                delivery_instructions = excluded.delivery_instructions,
                address_ids_json = excluded.address_ids_json,
                channel_detail_ids_json = excluded.channel_detail_ids_json,
                tags_json = excluded.tags_json,
                raw_payload_json = excluded.raw_payload_json,
                fetched_at = excluded.fetched_at,
                updated_at = excluded.updated_at
            """
            ,
            (
                job.source,
                job.job_id,
                job.url,
                job.title,
                job.location,
                job.category,
                job.category_id,
                job.target_audience,
                job.job_nature,
                job.job_nature_id,
                job.hire_type_name,
                job.hire_type_id,
                job.project_name,
                job.description,
                job.requirements,
                job.bonus_points,
                job.summary,
                job.delivery_instructions,
                json.dumps(job.address_ids, ensure_ascii=False),
                json.dumps(job.channel_detail_ids, ensure_ascii=False),
                json.dumps(job.tags, ensure_ascii=False),
                json.dumps(job.raw_payload, ensure_ascii=False),
                job.fetched_at,
                job.fetched_at,
            ),
        )

    def _write_raw_snapshot(self, bundle: CrawlBundle) -> Path:
        return self._write_batch_snapshot(
            source=bundle.source,
            prefix=bundle.primary_job.job_id,
            raw_snapshot=bundle.raw_snapshot,
            finished_at=bundle.finished_at,
        )

    def _upsert_weapon(self, connection: sqlite3.Connection, weapon: WeaponRecord) -> None:
        connection.execute(
            """
            INSERT INTO weapon_pages (
                source, item_id, url, title, item_type, rarity, ammo_type, firing_mode,
                arc_armor_penetration, magazine_size, quote, summary, infobox_tags_json,
                mod_slots_json, stats_json, sources_json, crafting_json, upgrading_json,
                repairing_json, recycling_json, price_comparison_json, history_json,
                raw_payload_json, fetched_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, item_id) DO UPDATE SET
                url = excluded.url,
                title = excluded.title,
                item_type = excluded.item_type,
                rarity = excluded.rarity,
                ammo_type = excluded.ammo_type,
                firing_mode = excluded.firing_mode,
                arc_armor_penetration = excluded.arc_armor_penetration,
                magazine_size = excluded.magazine_size,
                quote = excluded.quote,
                summary = excluded.summary,
                infobox_tags_json = excluded.infobox_tags_json,
                mod_slots_json = excluded.mod_slots_json,
                stats_json = excluded.stats_json,
                sources_json = excluded.sources_json,
                crafting_json = excluded.crafting_json,
                upgrading_json = excluded.upgrading_json,
                repairing_json = excluded.repairing_json,
                recycling_json = excluded.recycling_json,
                price_comparison_json = excluded.price_comparison_json,
                history_json = excluded.history_json,
                raw_payload_json = excluded.raw_payload_json,
                fetched_at = excluded.fetched_at,
                updated_at = excluded.updated_at
            """,
            (
                weapon.source,
                weapon.item_id,
                weapon.url,
                weapon.title,
                weapon.item_type,
                weapon.rarity,
                weapon.ammo_type,
                weapon.firing_mode,
                weapon.arc_armor_penetration,
                weapon.magazine_size,
                weapon.quote,
                weapon.summary,
                json.dumps(weapon.infobox_tags, ensure_ascii=False),
                json.dumps(weapon.mod_slots, ensure_ascii=False),
                json.dumps(weapon.stats, ensure_ascii=False),
                json.dumps(weapon.sources, ensure_ascii=False),
                json.dumps(weapon.crafting, ensure_ascii=False),
                json.dumps(weapon.upgrading, ensure_ascii=False),
                json.dumps(weapon.repairing, ensure_ascii=False),
                json.dumps(weapon.recycling, ensure_ascii=False),
                json.dumps(weapon.price_comparison, ensure_ascii=False),
                json.dumps(weapon.history, ensure_ascii=False),
                json.dumps(weapon.raw_payload, ensure_ascii=False),
                weapon.fetched_at,
                weapon.fetched_at,
            ),
        )

    def _upsert_arc_enemy(self, connection: sqlite3.Connection, enemy: ArcEnemyRecord) -> None:
        connection.execute(
            """
            INSERT INTO arc_enemy_pages (
                source, item_id, url, title, threat_level, armor, primary_attack, weakness,
                abilities, xp_gained, health, summary, attack_text, behavior_text,
                abilities_text, codex_entry, stats_json, combat_tips_json, loot_json,
                locations_json, history_json, changelog_json, trivia_json,
                achievement_tips_json, references_json, sections_json, raw_payload_json,
                fetched_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, item_id) DO UPDATE SET
                url = excluded.url,
                title = excluded.title,
                threat_level = excluded.threat_level,
                armor = excluded.armor,
                primary_attack = excluded.primary_attack,
                weakness = excluded.weakness,
                abilities = excluded.abilities,
                xp_gained = excluded.xp_gained,
                health = excluded.health,
                summary = excluded.summary,
                attack_text = excluded.attack_text,
                behavior_text = excluded.behavior_text,
                abilities_text = excluded.abilities_text,
                codex_entry = excluded.codex_entry,
                stats_json = excluded.stats_json,
                combat_tips_json = excluded.combat_tips_json,
                loot_json = excluded.loot_json,
                locations_json = excluded.locations_json,
                history_json = excluded.history_json,
                changelog_json = excluded.changelog_json,
                trivia_json = excluded.trivia_json,
                achievement_tips_json = excluded.achievement_tips_json,
                references_json = excluded.references_json,
                sections_json = excluded.sections_json,
                raw_payload_json = excluded.raw_payload_json,
                fetched_at = excluded.fetched_at,
                updated_at = excluded.updated_at
            """,
            (
                enemy.source,
                enemy.item_id,
                enemy.url,
                enemy.title,
                enemy.threat_level,
                enemy.armor,
                enemy.primary_attack,
                enemy.weakness,
                enemy.abilities,
                enemy.xp_gained,
                enemy.health,
                enemy.summary,
                enemy.attack_text,
                enemy.behavior_text,
                enemy.abilities_text,
                enemy.codex_entry,
                json.dumps(enemy.stats, ensure_ascii=False),
                json.dumps(enemy.combat_tips, ensure_ascii=False),
                json.dumps(enemy.loot, ensure_ascii=False),
                json.dumps(enemy.locations, ensure_ascii=False),
                json.dumps(enemy.history, ensure_ascii=False),
                json.dumps(enemy.changelog, ensure_ascii=False),
                json.dumps(enemy.trivia, ensure_ascii=False),
                json.dumps(enemy.achievement_tips, ensure_ascii=False),
                json.dumps(enemy.references, ensure_ascii=False),
                json.dumps(enemy.sections, ensure_ascii=False),
                json.dumps(enemy.raw_payload, ensure_ascii=False),
                enemy.fetched_at,
                enemy.fetched_at,
            ),
        )

    def _write_batch_snapshot(
        self,
        source: str,
        prefix: str,
        raw_snapshot: dict[str, Any],
        finished_at: str,
    ) -> Path:
        source_dir = RAW_DIR / source
        source_dir.mkdir(exist_ok=True)
        filename = f"{prefix}_{finished_at.replace(':', '-').replace('+', '_')}.json"
        path = source_dir / filename
        path.write_text(
            json.dumps(raw_snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def _ensure_job_columns(self, connection: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
        }
        wanted_columns = {
            "delivery_instructions": "TEXT DEFAULT ''",
            "ai_analysis": "TEXT DEFAULT ''",
            "ai_focus_score": "INTEGER DEFAULT 0",
            "ai_focus_level": "TEXT DEFAULT ''",
            "ai_focus_lane": "TEXT DEFAULT ''",
            "ai_focus_reason": "TEXT DEFAULT ''",
            "ai_focus_signals_json": "TEXT DEFAULT '[]'",
            "ai_focus_updated_at": "TEXT DEFAULT ''",
        }
        for column_name, column_spec in wanted_columns.items():
            if column_name not in columns:
                connection.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_spec}")

    def _load_json_or_default(self, value: Any) -> Any:
        if value in (None, ""):
            return []
        if isinstance(value, (list, dict)):
            return value
        return json.loads(value)
