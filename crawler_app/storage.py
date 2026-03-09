from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

import pandas as pd

from crawler_app.config import DB_PATH, RAW_DIR, ensure_directories
from crawler_app.models import CrawlBundle, JobRecord


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
                """
            )

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

        for column in ("address_ids_json", "channel_detail_ids_json", "tags_json", "raw_payload_json"):
            dataframe[column] = dataframe[column].map(json.loads)
        return dataframe

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

    def _upsert_job(self, connection: sqlite3.Connection, job: JobRecord) -> None:
        connection.execute(
            """
            INSERT INTO jobs (
                source, job_id, url, title, location, category, category_id, target_audience,
                job_nature, job_nature_id, hire_type_name, hire_type_id, project_name,
                description, requirements, bonus_points, summary, address_ids_json,
                channel_detail_ids_json, tags_json, raw_payload_json, fetched_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                json.dumps(job.address_ids, ensure_ascii=False),
                json.dumps(job.channel_detail_ids, ensure_ascii=False),
                json.dumps(job.tags, ensure_ascii=False),
                json.dumps(job.raw_payload, ensure_ascii=False),
                job.fetched_at,
                job.fetched_at,
            ),
        )

    def _write_raw_snapshot(self, bundle: CrawlBundle) -> Path:
        source_dir = RAW_DIR / bundle.source
        source_dir.mkdir(exist_ok=True)
        filename = f"{bundle.primary_job.job_id}_{bundle.finished_at.replace(':', '-').replace('+', '_')}.json"
        path = source_dir / filename
        path.write_text(
            json.dumps(bundle.raw_snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path
