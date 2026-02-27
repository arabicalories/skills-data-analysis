#!/usr/bin/env python3
"""Fetch yesterday's Umami basic metrics and funnel metrics."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_BASE_URL = "https://api.umami.is/v1"
DEFAULT_FUNNEL_NAMES = "pv -> login,pv -> purchase,guest trial,pricing"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)
DEFAULT_FUNNEL_DISPLAY_NAMES = {
    "pv -> login": "登录率",
    "pv -> purchase": "付费率",
    "guest trial": "试用率",
    "pricing": "价格查看率",
}


class UmamiApiError(RuntimeError):
    """Raised when Umami API request fails."""


@dataclass
class RangeInfo:
    day: date
    timezone_name: str
    local_start: datetime
    local_end: datetime
    utc_start: datetime
    utc_end: datetime

    @property
    def start_at_ms(self) -> int:
        return int(self.utc_start.timestamp() * 1000)

    @property
    def end_at_ms(self) -> int:
        return int(self.utc_end.timestamp() * 1000)


class UmamiClient:
    """Minimal Umami API client using urllib from stdlib."""

    def __init__(self, base_url: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = self._build_auth_headers()

    @staticmethod
    def _build_auth_headers() -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            # Cloudflare may block urllib's default User-Agent.
            "User-Agent": os.getenv("UMAMI_USER_AGENT", DEFAULT_USER_AGENT).strip()
            or DEFAULT_USER_AGENT,
        }
        api_key = os.getenv("UMAMI_API_KEY", "").strip()
        bearer_token = os.getenv("UMAMI_BEARER_TOKEN", "").strip()

        if api_key:
            headers["x-umami-api-key"] = api_key
            return headers
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
            return headers

        raise UmamiApiError(
            "Missing auth. Set UMAMI_API_KEY (cloud) or UMAMI_BEARER_TOKEN (self-hosted)."
        )

    def request(
        self,
        method: str,
        path: str,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if query:
            encoded_query = urllib.parse.urlencode(query, doseq=True)
            url = f"{url}?{encoded_query}"

        headers = dict(self.headers)
        payload = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url=url, data=payload, method=method, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise UmamiApiError(
                f"HTTP {exc.code} when calling {method} {url}: {err_body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise UmamiApiError(f"Failed to call {method} {url}: {exc}") from exc

        if not raw:
            return None

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise UmamiApiError(f"Non-JSON response from {method} {url}: {raw[:500]}") from exc

    def get_basic_stats(self, website_id: str, range_info: RangeInfo) -> dict[str, Any]:
        return self.request(
            "GET",
            f"websites/{website_id}/stats",
            query={
                "startAt": range_info.start_at_ms,
                "endAt": range_info.end_at_ms,
            },
        )

    def get_funnel_reports(self, website_id: str) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        page = 1
        page_size = 100

        while True:
            resp = self.request(
                "GET",
                "reports",
                query={
                    "websiteId": website_id,
                    "type": "funnel",
                    "page": page,
                    "pageSize": page_size,
                },
            )
            if not isinstance(resp, dict):
                break

            data = resp.get("data") or []
            if not isinstance(data, list) or not data:
                break

            reports.extend([item for item in data if isinstance(item, dict)])

            total_count = resp.get("count")
            current_page_size = resp.get("pageSize") or page_size
            if isinstance(total_count, int):
                if page * int(current_page_size) >= total_count:
                    break
            elif len(data) < page_size:
                break

            page += 1

        return reports

    def run_funnel(
        self,
        website_id: str,
        range_info: RangeInfo,
        steps: list[dict[str, Any]],
        window_minutes: int,
    ) -> list[dict[str, Any]]:
        payload = {
            "websiteId": website_id,
            "type": "funnel",
            "filters": {},
            "parameters": {
                "steps": steps,
                "window": window_minutes,
                "startDate": to_iso(range_info.utc_start),
                "endDate": to_iso(range_info.utc_end),
            },
        }

        data = self.request("POST", "reports/funnel", body=payload)
        if not isinstance(data, list):
            raise UmamiApiError(f"Unexpected funnel response type: {type(data).__name__}")
        return [row for row in data if isinstance(row, dict)]


def to_iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_target_day(day_str: str | None, tz_name: str) -> RangeInfo:
    tz = ZoneInfo(tz_name)
    if day_str:
        try:
            day = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError as exc:
            raise UmamiApiError(f"Invalid --day format: {day_str}. Use YYYY-MM-DD.") from exc
    else:
        day = datetime.now(tz).date() - timedelta(days=1)

    local_start = datetime.combine(day, time(0, 0, 0, 0), tzinfo=tz)
    local_end = datetime.combine(day, time(23, 59, 59, 999000), tzinfo=tz)
    utc_start = local_start.astimezone(timezone.utc)
    utc_end = local_end.astimezone(timezone.utc)

    return RangeInfo(
        day=day,
        timezone_name=tz_name,
        local_start=local_start,
        local_end=local_end,
        utc_start=utc_start,
        utc_end=utc_end,
    )


def parse_funnel_names(value: str) -> list[str]:
    return [name.strip() for name in value.split(",") if name.strip()]


def parse_report_map(raw_map: str | None) -> dict[str, str]:
    if not raw_map:
        return {}
    try:
        data = json.loads(raw_map)
    except json.JSONDecodeError as exc:
        raise UmamiApiError(f"Invalid --report-name-map JSON: {raw_map}") from exc
    if not isinstance(data, dict):
        raise UmamiApiError("--report-name-map must be a JSON object.")
    cleaned: dict[str, str] = {}
    for key, value in data.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise UmamiApiError("--report-name-map keys and values must be strings.")
        cleaned[key.strip()] = value.strip()
    return cleaned


def metric_value(stats: dict[str, Any], key: str) -> float:
    raw = stats.get(key)
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, dict):
        nested = raw.get("value")
        if isinstance(nested, (int, float)):
            return float(nested)
    return 0.0


def normalize_name(name: str) -> str:
    # Keep alphanumerics (and CJK letters), remove spaces/punctuation for fuzzy matching.
    return re.sub(r"[\W_]+", "", name.casefold(), flags=re.UNICODE)


def pick_report(target_name: str, reports: list[dict[str, Any]]) -> dict[str, Any] | None:
    target_exact = target_name.casefold()
    for report in reports:
        report_name = str(report.get("name", ""))
        if report_name.casefold() == target_exact:
            return report

    target_norm = normalize_name(target_name)
    if not target_norm:
        return None

    fuzzy_matches: list[dict[str, Any]] = []
    for report in reports:
        report_name = str(report.get("name", ""))
        report_norm = normalize_name(report_name)
        if not report_norm:
            continue
        if target_norm in report_norm or report_norm in target_norm:
            fuzzy_matches.append(report)

    if len(fuzzy_matches) == 1:
        return fuzzy_matches[0]
    return None


def format_duration(seconds: float) -> str:
    total = max(int(round(seconds)), 0)
    hrs = total // 3600
    mins = (total % 3600) // 60
    secs = total % 60
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"


def build_summary(
    range_info: RangeInfo,
    basic_stats: dict[str, Any],
    funnel_results: list[dict[str, Any]],
    available_report_names: list[str],
    website_id: str,
) -> dict[str, Any]:
    visitors = int(metric_value(basic_stats, "visitors"))
    visits = int(metric_value(basic_stats, "visits"))
    # Umami stats.totaltime is reported in seconds (not milliseconds).
    total_time_seconds = float(metric_value(basic_stats, "totaltime"))
    avg_visit_duration_seconds = (total_time_seconds / visits) if visits else 0.0

    return {
        "source": "Umami",
        "website_id": website_id,
        "date": str(range_info.day),
        "timezone": range_info.timezone_name,
        "time_range": {
            "local_start": range_info.local_start.isoformat(),
            "local_end": range_info.local_end.isoformat(),
            "utc_start": to_iso(range_info.utc_start),
            "utc_end": to_iso(range_info.utc_end),
            "start_at_ms": range_info.start_at_ms,
            "end_at_ms": range_info.end_at_ms,
        },
        "basic_data": {
            "visitors": visitors,
            "visits": visits,
            "visit_duration_seconds": round(avg_visit_duration_seconds, 2),
            "visit_duration_hhmmss": format_duration(avg_visit_duration_seconds),
            "totaltime_seconds": round(total_time_seconds, 2),
        },
        "funnel_data": funnel_results,
        "available_funnel_reports": available_report_names,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    basic = summary["basic_data"]
    lines: list[str] = [
        "Umami",
        "基础数据",
        f"- Date: {summary['date']} ({summary['timezone']})",
        f"- Visitors: {basic['visitors']}",
        f"- Visits: {basic['visits']}",
        f"- Visit duration: {basic['visit_duration_hhmmss']} ({basic['visit_duration_seconds']}s)",
        "",
        "漏斗数据",
    ]

    funnels = summary.get("funnel_data", [])
    if not funnels:
        lines.append("- No funnel results.")
        return "\n".join(lines)

    for item in funnels:
        display_name = item.get("display_name", item.get("requested_name", "unknown"))
        status = item.get("status")

        if status != "ok":
            lines.append(
                f"- {display_name}: status={status}, note={item.get('note', 'unknown issue')}"
            )
            continue

        start = item.get("start_visitors", 0)
        final = item.get("final_visitors", 0)
        rate = item.get("conversion_rate")
        rate_str = "n/a" if rate is None else f"{rate * 100:.2f}%"
        lines.append(f"- {display_name}: {start} -> {final}, conversion={rate_str}")

    return "\n".join(lines)


def run_funnels(
    client: UmamiClient,
    website_id: str,
    range_info: RangeInfo,
    target_names: list[str],
    report_map: dict[str, str],
) -> tuple[list[dict[str, Any]], list[str]]:
    reports = client.get_funnel_reports(website_id)
    available_names = [str(report.get("name", "")) for report in reports if report.get("name")]

    results: list[dict[str, Any]] = []
    for requested_name in target_names:
        display_name = DEFAULT_FUNNEL_DISPLAY_NAMES.get(requested_name, requested_name)
        lookup_name = report_map.get(requested_name, requested_name)
        report = pick_report(lookup_name, reports)
        if not report:
            results.append(
                {
                    "requested_name": requested_name,
                    "display_name": display_name,
                    "lookup_name": lookup_name,
                    "status": "missing_report",
                    "note": "No matching configured funnel report found.",
                }
            )
            continue

        report_name = str(report.get("name", ""))
        report_id = str(report.get("reportId", ""))
        parameters = report.get("parameters") or {}
        steps = parameters.get("steps")
        window = parameters.get("window")

        if not isinstance(steps, list) or not steps:
            results.append(
                {
                    "requested_name": requested_name,
                    "display_name": display_name,
                    "lookup_name": lookup_name,
                    "matched_report_name": report_name,
                    "report_id": report_id,
                    "status": "invalid_report",
                    "note": "Report parameters.steps is missing or invalid.",
                }
            )
            continue

        if not isinstance(window, int) or window <= 0:
            window = 60

        try:
            raw_steps = client.run_funnel(
                website_id=website_id,
                range_info=range_info,
                steps=steps,
                window_minutes=window,
            )
        except UmamiApiError as exc:
            results.append(
                {
                    "requested_name": requested_name,
                    "display_name": display_name,
                    "lookup_name": lookup_name,
                    "matched_report_name": report_name,
                    "report_id": report_id,
                    "status": "request_failed",
                    "note": str(exc),
                }
            )
            continue

        parsed_steps: list[dict[str, Any]] = []
        prev_visitors: int | None = None
        for index, row in enumerate(raw_steps, start=1):
            step_visitors = int(row.get("visitors") or 0)
            step_item = {
                "step_index": index,
                "step_type": row.get("type"),
                "step_value": row.get("value"),
                "step_label": f"step_{index}",
                "visitors": step_visitors,
                "dropoff": int(row.get("dropoff") or 0),
            }
            if prev_visitors is None or prev_visitors == 0:
                step_item["rate_from_previous"] = None
            else:
                step_item["rate_from_previous"] = step_visitors / prev_visitors
            parsed_steps.append(step_item)
            prev_visitors = step_visitors

        start_visitors = parsed_steps[0]["visitors"] if parsed_steps else 0
        final_visitors = parsed_steps[-1]["visitors"] if parsed_steps else 0
        conversion_rate = None if start_visitors == 0 else (final_visitors / start_visitors)

        results.append(
            {
                "requested_name": requested_name,
                "display_name": display_name,
                "lookup_name": lookup_name,
                "matched_report_name": report_name,
                "report_id": report_id,
                "status": "ok",
                "start_visitors": start_visitors,
                "final_visitors": final_visitors,
                "conversion_rate": conversion_rate,
                "steps": parsed_steps,
            }
        )

    return results, available_names


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch Umami daily summary for yesterday (basic metrics + configured funnel metrics)."
        )
    )
    parser.add_argument(
        "--base-url",
        default=os.getenv("UMAMI_BASE_URL", DEFAULT_BASE_URL),
        help="Umami API base URL. Example cloud: https://api.umami.is/v1",
    )
    parser.add_argument(
        "--website-id",
        default=os.getenv("UMAMI_WEBSITE_ID", ""),
        help="Umami websiteId. Defaults to UMAMI_WEBSITE_ID env.",
    )
    parser.add_argument(
        "--timezone",
        default=os.getenv("UMAMI_TIMEZONE", "UTC"),
        help="Timezone for day boundary. Defaults to UMAMI_TIMEZONE or UTC.",
    )
    parser.add_argument(
        "--day",
        default=None,
        help="Day in YYYY-MM-DD. Defaults to yesterday in selected timezone.",
    )
    parser.add_argument(
        "--funnel-names",
        default=os.getenv("UMAMI_FUNNEL_NAMES", DEFAULT_FUNNEL_NAMES),
        help=(
            "Comma-separated target funnel names. "
            f"Default: {DEFAULT_FUNNEL_NAMES}"
        ),
    )
    parser.add_argument(
        "--report-name-map",
        default=os.getenv("UMAMI_FUNNEL_REPORT_MAP", ""),
        help="JSON object mapping requested funnel names to actual dashboard report names.",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Write output to file path instead of stdout.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="HTTP timeout in seconds. Default 30.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    website_id = args.website_id.strip()
    if not website_id:
        print("Missing website id. Set --website-id or UMAMI_WEBSITE_ID.", file=sys.stderr)
        return 2

    try:
        range_info = parse_target_day(args.day, args.timezone)
        target_names = parse_funnel_names(args.funnel_names)
        report_map = parse_report_map(args.report_name_map)
        client = UmamiClient(args.base_url, timeout=args.timeout)

        basic_stats = client.get_basic_stats(website_id, range_info)
        funnel_results, available_names = run_funnels(
            client=client,
            website_id=website_id,
            range_info=range_info,
            target_names=target_names,
            report_map=report_map,
        )

        summary = build_summary(
            range_info=range_info,
            basic_stats=basic_stats,
            funnel_results=funnel_results,
            available_report_names=available_names,
            website_id=website_id,
        )

        if args.format == "json":
            rendered = json.dumps(summary, ensure_ascii=False, indent=2)
        else:
            rendered = render_markdown(summary)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as fp:
                fp.write(rendered + "\n")
        else:
            print(rendered)
        return 0
    except (UmamiApiError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
