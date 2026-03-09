from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

import httpx

from crawler_app.config import DEFAULT_TARGET, HTTP_TIMEOUT_SECONDS, MIHOYO_API_BASE, MIHOYO_JOB_URL
from crawler_app.connectors.base import BaseConnector, ConnectorError
from crawler_app.models import CrawlBundle, JobRecord, RelatedJob

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - optional fallback
    sync_playwright = None


class MihoyoJobsConnector(BaseConnector):
    source = "mihoyo_jobs"
    display_name = "miHoYo 校园招聘"
    data_kind = "招聘岗位"
    description = "抓取 miHoYo 校招岗位详情、相似岗位列表和原始接口响应。"
    default_target = DEFAULT_TARGET

    def __init__(self) -> None:
        self.client = httpx.Client(
            base_url=MIHOYO_API_BASE,
            timeout=HTTP_TIMEOUT_SECONDS,
            headers={
                "Content-Type": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
                ),
                "Referer": "https://jobs.mihoyo.com/",
            },
        )

    def crawl(self, target: str, related_limit: int = 10) -> CrawlBundle:
        started_at = datetime.now(timezone.utc).isoformat()
        job_id = self.resolve_job_id(target)

        try:
            primary_payload = self._fetch_job_payload(job_id)
            related_payloads = self._fetch_related_payloads(primary_payload, related_limit)
        except Exception as error:
            if sync_playwright is None:
                raise ConnectorError(f"API 抓取失败，且 Playwright 不可用: {error}") from error
            primary_payload, related_payloads = self._fetch_with_browser(job_id, related_limit)

        primary_job = self._build_job(primary_payload)
        related_jobs = [self._build_job(payload) for payload in related_payloads]
        related_links = [
            RelatedJob(
                source_job_id=primary_job.job_id,
                related_job_id=job.job_id,
                rank_order=index,
                related_title=job.title,
            )
            for index, job in enumerate(related_jobs, start=1)
        ]
        finished_at = datetime.now(timezone.utc).isoformat()

        return CrawlBundle(
            source=self.source,
            target=target,
            primary_job=primary_job,
            related_jobs=related_jobs,
            related_links=related_links,
            raw_snapshot={
                "target": target,
                "resolved_job_id": job_id,
                "primary_payload": primary_payload,
                "related_payloads": related_payloads,
            },
            started_at=started_at,
            finished_at=finished_at,
        )

    def resolve_job_id(self, target: str) -> str:
        value = target.strip()
        match = re.search(r"/position/(\d+)", value)
        if match:
            return match.group(1)
        if value.isdigit():
            return value
        raise ConnectorError(f"无法从目标中解析岗位 ID: {target}")

    def _fetch_job_payload(self, job_id: str) -> dict[str, Any]:
        response = self._post("/v1/job/info", {"id": job_id, "channelDetailIds": [1], "hireType": 1})
        return response["data"]

    def fetch_category_counts(self, internships_only: bool = True) -> list[dict[str, Any]]:
        response = self._post("/v1/job/category/list", {"channelDetailIds": [1], "hireType": 1})
        items = list(response.get("data", []))
        if internships_only:
            internship_counts = self.fetch_counts_from_list(job_natures=[3])
            for item in items:
                item["count"] = internship_counts.get(str(item.get("competencyType", "")), 0)
        return items

    def fetch_jobs_by_filters(
        self,
        competency_types: list[str] | None = None,
        job_natures: list[int] | None = None,
    ) -> tuple[list[JobRecord], dict[str, Any]]:
        first_page = self._fetch_job_list_page(
            page_no=1,
            page_size=100,
            competency_types=competency_types,
            job_natures=job_natures,
        )
        total = int(first_page["data"]["total"])
        pages = (total + 99) // 100
        list_items = list(first_page["data"].get("list", []))
        for page_no in range(2, pages + 1):
            page_payload = self._fetch_job_list_page(
                page_no=page_no,
                page_size=100,
                competency_types=competency_types,
                job_natures=job_natures,
            )
            list_items.extend(page_payload["data"].get("list", []))

        jobs: list[JobRecord] = []
        job_ids: list[str] = []
        for item in list_items:
            job_id = str(item["id"])
            job_ids.append(job_id)
            jobs.append(self._build_job(self._fetch_job_payload(job_id)))

        return jobs, {
            "mode": "batch",
            "filters": {
                "competency_types": competency_types or [],
                "job_natures": job_natures or [],
            },
            "total": total,
            "job_ids": job_ids,
        }

    def fetch_counts_from_list(self, job_natures: list[int] | None = None) -> dict[str, int]:
        first_page = self._fetch_job_list_page(
            page_no=1,
            page_size=100,
            competency_types=None,
            job_natures=job_natures,
        )
        total = int(first_page["data"]["total"])
        pages = (total + 99) // 100
        counts: dict[str, int] = {}
        for page_no in range(1, pages + 1):
            payload = first_page if page_no == 1 else self._fetch_job_list_page(
                page_no=page_no,
                page_size=100,
                competency_types=None,
                job_natures=job_natures,
            )
            for item in payload["data"].get("list", []):
                key = self._competency_name_to_id(item.get("competencyType", ""))
                counts[key] = counts.get(key, 0) + 1
        return counts

    def _fetch_related_payloads(self, primary_payload: dict[str, Any], related_limit: int) -> list[dict[str, Any]]:
        filters = {
            "pageNo": 1,
            "pageSize": max(1, min(related_limit, 50)),
            "currentJobId": primary_payload["id"],
            "addressIds": [item["addressId"] for item in primary_payload.get("addressDetailList", [])],
            "competencyTypes": [primary_payload.get("competencyTypeId")],
            "jobNatures": [primary_payload.get("jobNatureId")],
            "channelDetailIds": [1],
            "hireType": primary_payload.get("hireType", 1),
        }
        response = self._post("/v1/job/list", filters)
        payloads: list[dict[str, Any]] = []
        for item in response["data"].get("list", []):
            payloads.append(self._fetch_job_payload(item["id"]))
        return payloads

    def _fetch_with_browser(self, job_id: str, related_limit: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        captured: dict[str, Any] = {"info": None, "related": []}
        target_url = MIHOYO_JOB_URL.format(job_id=job_id)

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()

            def on_response(response: Any) -> None:
                if "/v1/job/info" in response.url:
                    body = response.json()
                    if body.get("success"):
                        captured["info"] = body["data"]
                if "/v1/job/list" in response.url:
                    body = response.json()
                    if body.get("success"):
                        captured["related"] = body["data"].get("list", [])[:related_limit]

            page.on("response", on_response)
            page.goto(target_url, wait_until="networkidle", timeout=60000)
            browser.close()

        if not captured["info"]:
            raise ConnectorError("Playwright 未能抓到岗位详情接口响应。")

        primary_payload = captured["info"]
        related_payloads: list[dict[str, Any]] = []
        for item in captured["related"]:
            try:
                related_payloads.append(self._fetch_job_payload(item["id"]))
            except Exception:
                related_payloads.append(
                    {
                        "id": item["id"],
                        "title": item.get("title", ""),
                        "addressDetailList": item.get("addressDetailList", []),
                        "competencyType": item.get("competencyType", ""),
                        "competencyTypeId": "",
                        "jobNature": item.get("jobNature", ""),
                        "jobNatureId": item.get("jobNatureId", 0),
                        "objectName": item.get("objectName", ""),
                        "projectName": item.get("projectName", ""),
                        "hireType": 1,
                        "hireTypeName": "校园招聘",
                        "description": "",
                        "jobRequire": "",
                        "addition": "",
                        "jobSummary": item.get("jobSummary", ""),
                        "channelDetailIds": item.get("channelDetailIds", [1]),
                    }
                )
        return primary_payload, related_payloads

    def _build_job(self, payload: dict[str, Any]) -> JobRecord:
        location = " / ".join(
            item["addressDetail"] for item in payload.get("addressDetailList", []) if isinstance(item, dict) and item.get("addressDetail")
        )
        tags = self._normalize_tags(payload.get("tagList", []))
        return JobRecord(
            source=self.source,
            job_id=str(payload["id"]),
            url=MIHOYO_JOB_URL.format(job_id=payload["id"]),
            title=self._normalize_text(payload.get("title", "")),
            location=location,
            category=self._normalize_text(payload.get("competencyType", "")),
            category_id=str(payload.get("competencyTypeId", "")),
            target_audience=self._normalize_text(payload.get("objectName", "")),
            job_nature=self._normalize_text(payload.get("jobNature", "")),
            job_nature_id=int(payload.get("jobNatureId", 0) or 0),
            hire_type_name=self._normalize_text(payload.get("hireTypeName", "")),
            hire_type_id=int(payload.get("hireType", 0) or 0),
            project_name=self._normalize_text(payload.get("projectName", "")),
            description=self._normalize_text(payload.get("description", "")),
            requirements=self._normalize_text(payload.get("jobRequire", "")),
            bonus_points=self._normalize_text(payload.get("addition", "")),
            summary=self._normalize_text(payload.get("jobSummary", "")),
            delivery_instructions=self._normalize_text(payload.get("deliveryInstructions", "")),
            address_ids=[
                str(item["addressId"])
                for item in payload.get("addressDetailList", [])
                if isinstance(item, dict) and item.get("addressId") is not None
            ],
            channel_detail_ids=list(payload.get("channelDetailIds", [])),
            tags=tags,
            raw_payload=payload,
        )

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.client.post(path, json=payload)
        response.raise_for_status()
        body = response.json()
        if not body.get("success"):
            raise ConnectorError(f"接口返回失败: {path} -> {body}")
        return body

    def _fetch_job_list_page(
        self,
        page_no: int,
        page_size: int,
        competency_types: list[str] | None,
        job_natures: list[int] | None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "pageNo": page_no,
            "pageSize": page_size,
            "channelDetailIds": [1],
            "hireType": 1,
        }
        if competency_types:
            payload["competencyTypes"] = competency_types
        if job_natures:
            payload["jobNatures"] = job_natures
        return self._post("/v1/job/list", payload)

    def _normalize_tags(self, raw_tags: Any) -> list[str]:
        if not isinstance(raw_tags, list):
            return []

        normalized: list[str] = []
        for item in raw_tags:
            tag = ""
            if isinstance(item, str):
                tag = item.strip()
            elif isinstance(item, dict):
                for key in ("name", "tagName", "label", "value"):
                    value = item.get(key)
                    if isinstance(value, str) and value.strip():
                        tag = value.strip()
                        break
            if tag and tag not in normalized:
                normalized.append(tag)
        return normalized

    def _normalize_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return "\n".join(str(item).strip() for item in value if str(item).strip())
        return str(value).strip()

    def _competency_name_to_id(self, competency_name: str) -> str:
        mapping = {
            "程序&技术类": "1",
            "美术&表现类": "2",
            "产品策划类": "3",
            "质量管理类": "4",
            "运营类": "5",
            "市场&商务类": "6",
            "综合类": "7",
            "国际化类": "8",
        }
        return mapping.get(competency_name, "")
