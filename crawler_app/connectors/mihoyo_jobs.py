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
        location = " / ".join(item["addressDetail"] for item in payload.get("addressDetailList", []))
        tags = [item.get("name", "") for item in payload.get("tagList", []) if item.get("name")]
        return JobRecord(
            source=self.source,
            job_id=str(payload["id"]),
            url=MIHOYO_JOB_URL.format(job_id=payload["id"]),
            title=payload.get("title", ""),
            location=location,
            category=payload.get("competencyType", ""),
            category_id=str(payload.get("competencyTypeId", "")),
            target_audience=payload.get("objectName", ""),
            job_nature=payload.get("jobNature", ""),
            job_nature_id=int(payload.get("jobNatureId", 0) or 0),
            hire_type_name=payload.get("hireTypeName", ""),
            hire_type_id=int(payload.get("hireType", 0) or 0),
            project_name=payload.get("projectName", ""),
            description=payload.get("description", ""),
            requirements=payload.get("jobRequire", ""),
            bonus_points=payload.get("addition", ""),
            summary=payload.get("jobSummary", ""),
            address_ids=[item["addressId"] for item in payload.get("addressDetailList", [])],
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
