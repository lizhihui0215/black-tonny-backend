from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.erp_research_service import (
    analyze_response_payload,
    build_exploration_cases,
    get_exploration_strategy,
    get_exploration_target_titles,
    should_persist_capture,
    summarize_exploration_results,
)


SAMPLES_DIR = PROJECT_ROOT / "tmp" / "capture-samples"
REPORT_DOC_PATH = SAMPLES_DIR / "report_api_samples.md"
README_PATH = SAMPLES_DIR / "README.md"
DEFAULT_SESSION_PATH = SAMPLES_DIR / "yeusoft_session.json"
RAW_OUTPUT_ROOT = SAMPLES_DIR / "raw"
EXPLORATION_OUTPUT_ROOT = SAMPLES_DIR / "exploration"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")

LOGIN_COMPANY_URL = "https://jyapi.yeusoft.net/JyApi/Authorize/CompanyUserPassWord"
LOGIN_URL = "https://jyapi.yeusoft.net/JyApi/Authorize/Login"

TITLE_TO_SOURCE_ENDPOINT = {
    "零售明细统计": "yeusoft.report.retail_detail_stats",
    "导购员报表": "yeusoft.report.guide_sales_report",
    "店铺零售清单": "yeusoft.report.store_retail_list",
    "销售清单": "yeusoft.report.sales_list",
    "库存明细统计": "yeusoft.report.inventory_detail_stats",
    "库存零售统计": "yeusoft.report.inventory_sales_stats",
    "库存总和分析-按年份季节": "yeusoft.report.inventory_summary_by_year_season",
    "库存总和分析-按中分类": "yeusoft.report.inventory_summary_by_middle_category",
    "库存总和分析-按波段": "yeusoft.report.inventory_summary_by_band",
    "库存多维分析": "yeusoft.report.inventory_multi_dimension",
    "进销存统计": "yeusoft.report.stock_flow_stats",
    "出入库单据": "yeusoft.report.stock_movement_docs",
    "日进销存": "yeusoft.report.daily_stock_flow",
    "会员总和分析": "yeusoft.report.vip_summary",
    "会员消费排行": "yeusoft.report.vip_sales_rank",
    "储值按店汇总": "yeusoft.report.stored_value_by_store",
    "储值卡汇总": "yeusoft.report.stored_value_card_summary",
    "储值卡明细": "yeusoft.report.stored_value_card_detail",
    "商品销售情况": "yeusoft.report.product_sales_snapshot",
    "商品品类分析": "yeusoft.report.product_category_analysis",
    "门店销售月报": "yeusoft.report.store_monthly_sales",
    "每日流水单": "yeusoft.report.daily_payment_slip",
    "会员中心": "yeusoft.report.vip_center",
}


@dataclass
class ReportSpec:
    title: str
    url: str
    payload: dict[str, Any] | list[Any] | str
    method: str = "POST"

    @property
    def source_endpoint(self) -> str:
        return TITLE_TO_SOURCE_ENDPOINT.get(self.title, f"yeusoft.report.{slugify(self.title)}")

    @property
    def filename(self) -> str:
        return f"{slugify(self.title)}.json"


@dataclass
class AuthContext:
    source: str
    token: str
    refresh_token: str | None = None
    api_base_url: str | None = None
    company_code: str | None = None
    dept_code: str | None = None
    dept_name: str | None = None
    user_name: str | None = None
    phone: str | None = None
    session_path: Path | None = None
    raw_login_data: dict[str, Any] | None = None


def now_local() -> datetime:
    return datetime.now(LOCAL_TZ)


def slugify(value: str) -> str:
    value = value.strip()
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "report"


def read_login_credentials(readme_path: Path) -> tuple[str, str]:
    text = readme_path.read_text("utf-8")
    phone_match = re.search(r"账号[:：]\s*([0-9]+)", text)
    password_match = re.search(r"密码[:：]\s*([^\s]+)", text)
    if not phone_match or not password_match:
        raise ValueError(f"未能从 {readme_path} 解析账号或密码")
    return phone_match.group(1), password_match.group(1)


def parse_data_raw(block: str) -> dict[str, Any] | list[Any] | str:
    match = re.search(r"--data-raw\s+(\$?)(['\"])(.*)\2", block, re.DOTALL)
    if not match:
        return {}
    raw = match.group(3).strip()
    if match.group(1) == "$":
        raw = bytes(raw, "utf-8").decode("unicode_escape")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def parse_report_specs(doc_path: Path) -> list[ReportSpec]:
    text = doc_path.read_text("utf-8")
    pattern = re.compile(r"^###\s+(.+?)\n+```bash\n(.*?)```", re.MULTILINE | re.DOTALL)
    specs: list[ReportSpec] = []
    for title, block in pattern.findall(text):
        if title in {"CompanyUserPassWord", "Login"}:
            continue
        url_match = re.search(r"curl\s+'([^']+)'", block)
        if not url_match:
            continue
        specs.append(
            ReportSpec(
                title=title.strip(),
                url=url_match.group(1).strip(),
                payload=parse_data_raw(block),
            )
        )
    return specs


def no_proxy_opener() -> request.OpenerDirector:
    return request.build_opener(request.ProxyHandler({}))


def no_proxy_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
    ):
        env.pop(key, None)
    return env


def post_json(url: str, payload: dict[str, Any] | list[Any], headers: dict[str, str] | None = None) -> tuple[int, Any]:
    opener = no_proxy_opener()
    req_headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://jypos.yeusoft.net",
        "referer": "https://jypos.yeusoft.net/",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    }
    if headers:
        req_headers.update(headers)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, headers=req_headers, method="POST")
    with opener.open(req, timeout=60) as response:
        raw = response.read().decode("utf-8", "ignore")
        try:
            return response.status, json.loads(raw)
        except json.JSONDecodeError:
            return response.status, {"raw_text": raw}


def curl_post_json(url: str, payload: dict[str, Any] | list[Any], headers: dict[str, str] | None = None) -> tuple[int, Any]:
    req_headers = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en-US;q=0.8",
        "content-type": "application/json;charset=UTF-8",
        "origin": "https://jypos.yeusoft.net",
        "priority": "u=1, i",
        "referer": "https://jypos.yeusoft.net/",
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    }
    if headers:
        req_headers.update(headers)

    command = [
        "curl",
        "--silent",
        "--show-error",
        "--http1.1",
        "--request",
        "POST",
        url,
    ]
    for key, value in req_headers.items():
        command.extend(["-H", f"{key}: {value}"])
    command.extend(
        [
            "--data-raw",
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            "--write-out",
            "\n__STATUS__:%{http_code}",
        ]
    )

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        env=no_proxy_env(),
        check=False,
    )
    output = completed.stdout or ""
    marker = "\n__STATUS__:"
    if marker not in output:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(f"curl 请求失败: {stderr or '未返回状态码'}")
    body, _, status_text = output.rpartition(marker)
    status = int(status_text.strip() or "0")
    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        raise RuntimeError(f"curl 返回非零状态 {completed.returncode}: {stderr}")
    try:
        return status, json.loads(body)
    except json.JSONDecodeError:
        return status, {"raw_text": body}


def fetch_company_code(phone: str, password: str) -> str:
    status, payload = post_json(
        LOGIN_COMPANY_URL,
        {
            "MovePhone": phone,
            "Password": password,
            "Device": "codex-capture",
            "RegistrationID": "codex-capture",
        },
    )
    if status != 200 or not payload.get("Success"):
        raise RuntimeError(f"获取公司代码失败: {payload}")
    companies = payload.get("Data") or []
    if not companies:
        raise RuntimeError("登录成功但未返回公司代码")
    return str(companies[0]["Code"])


def login(phone: str, password: str, company_code: str) -> dict[str, Any]:
    opener = no_proxy_opener()
    request_payload = {
        "MovePhone": phone,
        "Password": password,
        "Code": company_code,
        "Platform": "JyPos",
        "Device": "codex-capture",
        "RegistrationID": "codex-capture",
    }
    req = request.Request(
        LOGIN_URL,
        data=json.dumps(request_payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json;charset=UTF-8",
            "origin": "https://jypos.yeusoft.net",
            "referer": "https://jypos.yeusoft.net/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        },
        method="POST",
    )
    with opener.open(req, timeout=60) as response:
        raw = response.read().decode("utf-8", "ignore")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"登录返回非 JSON: {raw[:300]}") from exc
        if response.status != 200 or not payload.get("Success"):
            raise RuntimeError(f"登录失败: {payload}")
        data = payload.get("Data") or {}
        access_token = response.headers.get("access-token") or data.get("AccessToken")
        refresh_token = response.headers.get("x-access-token")
        if not access_token:
            raise RuntimeError("登录成功但未返回 access-token")
        data["AccessToken"] = access_token
        if refresh_token:
            data["RefreshToken"] = refresh_token
        return data


def read_session_auth(session_path: Path) -> AuthContext:
    payload = json.loads(session_path.read_text("utf-8"))
    token = payload.get("yis_pc_token")
    if not token:
        raise ValueError(f"{session_path} 缺少 yis_pc_token")

    login_data_raw = payload.get("yis_pc_logindata") or ""
    login_data: dict[str, Any] = {}
    if login_data_raw:
        try:
            login_data = json.loads(login_data_raw)
        except json.JSONDecodeError:
            login_data = {}

    return AuthContext(
        source="session",
        token=token,
        refresh_token=payload.get("yis_v2_refreshToken"),
        api_base_url=payload.get("YIS_API_ERP_TEMP") or payload.get("yisapiurl"),
        company_code=payload.get("yis_pc_comcode") or login_data.get("ComCode"),
        dept_code=payload.get("yis_pc_DeptCode") or login_data.get("DeptCode"),
        dept_name=payload.get("yis_pc_deptName") or login_data.get("DeptName"),
        user_name=payload.get("yis_pc_userName") or login_data.get("UserName"),
        session_path=session_path,
        raw_login_data=login_data,
    )


def read_login_auth(readme_path: Path) -> AuthContext:
    phone, password = read_login_credentials(readme_path)
    company_code = fetch_company_code(phone, password)
    login_data = login(phone, password, company_code)
    return AuthContext(
        source="login",
        token=login_data["AccessToken"],
        refresh_token=login_data.get("RefreshToken"),
        api_base_url=login_data.get("JyApiUrl"),
        company_code=company_code,
        dept_code=login_data.get("DeptCode"),
        dept_name=login_data.get("DeptName"),
        user_name=login_data.get("UserName"),
        phone=phone,
        raw_login_data=login_data,
    )


def resolve_auth_context(auth_source: str, readme_path: Path, session_path: Path) -> AuthContext:
    if auth_source == "session":
        return read_session_auth(session_path)
    if auth_source == "login":
        return read_login_auth(readme_path)
    try:
        return read_login_auth(readme_path)
    except Exception:
        if session_path.exists():
            return read_session_auth(session_path)
        raise


def build_refresh_payload() -> dict[str, str]:
    return {
        "Device": f"{hashlib.md5(f'codex-{random.random()}'.encode()).hexdigest()}_codex",
        "RegistrationID": str(uuid.uuid4()),
        "Platform": "JyPos",
    }


def refresh_session_access_token(auth: AuthContext) -> tuple[str, int | None]:
    if not auth.refresh_token:
        raise RuntimeError("当前会话缺少 yis_v2_refreshToken，无法刷新 ERP access token")

    refresh_payload = build_refresh_payload()
    opener = no_proxy_opener()
    req = request.Request(
        f"{LOGIN_URL.rsplit('/', 1)[0]}/RefreshToken",
        data=json.dumps(refresh_payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=utf-8",
            "Authorization": f"Bearer {auth.token}",
            "X-Authorization": f"Bearer {auth.refresh_token}",
        },
        method="POST",
    )
    with opener.open(req, timeout=60) as response:
        raw = response.read().decode("utf-8", "ignore")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"刷新 access token 返回非 JSON: {raw[:300]}") from exc
        if response.status != 200 or not payload.get("Success"):
            raise RuntimeError(f"刷新 access token 失败: {payload}")
        access_token = response.headers.get("access-token")
        if not access_token:
            raise RuntimeError("刷新成功但响应头缺少 access-token")
        expired_time = None
        try:
            expired_time = (payload.get("Data") or {}).get("ExpiredTime")
        except Exception:
            expired_time = None
        return access_token, expired_time


def persist_session_refresh(auth: AuthContext, new_access_token: str, expired_time: int | None) -> None:
    if not auth.session_path or not auth.session_path.exists():
        return
    data = json.loads(auth.session_path.read_text("utf-8"))
    data["yis_pc_token"] = new_access_token
    if expired_time is not None:
        data["yis_v2_refreshToken.expiredTime"] = int(expired_time) * 1000
    auth.session_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")


def build_report_auth_headers(url: str, token: str) -> dict[str, str]:
    if "/JyApi/" in url:
        return {"Authorization": f"Bearer {token}"}
    return {"token": token}


def maybe_override_url(spec: ReportSpec, api_base_url: str | None) -> str:
    if not api_base_url:
        return spec.url
    parsed = parse.urlparse(spec.url)
    if parsed.netloc.endswith("yeusoft.net") and "/JyApi/" not in parsed.path:
        base = parse.urlparse(api_base_url)
        return parse.urlunparse((base.scheme, base.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))
    return spec.url


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), "utf-8")


def try_create_capture_batch(source_name: str) -> str | None:
    try:
        from app.services.batch_service import create_capture_batch

        return create_capture_batch(source_name=source_name)
    except Exception as exc:  # pragma: no cover - best effort path for offline/dev machines
        print(f"[warn] capture 库不可用，改为仅落本地文件: {exc}", file=sys.stderr)
        return None


def append_capture_payload_safe(
    capture_batch_id: str,
    *,
    source_endpoint: str,
    payload: dict[str, Any] | list[Any],
    request_params: dict[str, Any] | None = None,
    page_no: int | None = None,
) -> None:
    from app.services.batch_service import append_capture_payload

    append_capture_payload(
        capture_batch_id,
        source_endpoint=source_endpoint,
        payload=payload,
        request_params=request_params,
        page_no=page_no,
    )


def update_capture_batch_safe(capture_batch_id: str, **kwargs: Any) -> None:
    from app.services.batch_service import update_capture_batch

    update_capture_batch(capture_batch_id, **kwargs)


def perform_request(
    transport: str,
    url: str,
    payload: dict[str, Any] | list[Any],
    headers: dict[str, str],
) -> tuple[int, Any]:
    if transport == "curl":
        return curl_post_json(url, payload, headers=headers)
    return post_json(url, payload, headers=headers)


def bootstrap_capture_batch(
    capture_batch_id: str | None,
    auth: AuthContext,
    company_code: str,
    api_base_url: str | None,
) -> None:
    if not capture_batch_id:
        return
    if auth.source == "login":
        append_capture_payload_safe(
            capture_batch_id,
            source_endpoint="yeusoft.authorize.company_user_password",
            payload={"company_code": company_code},
            request_params={"phone": auth.phone, "device": "codex-capture"},
        )
        append_capture_payload_safe(
            capture_batch_id,
            source_endpoint="yeusoft.authorize.login",
            payload={
                "MovePhone": auth.raw_login_data.get("MovePhone") if auth.raw_login_data else None,
                "UserName": auth.user_name,
                "DeptName": auth.dept_name,
                "DeptCode": auth.dept_code,
                "JyApiUrl": auth.raw_login_data.get("JyApiUrl") if auth.raw_login_data else None,
                "JyApiV2": auth.raw_login_data.get("JyApiV2") if auth.raw_login_data else None,
                "Version": auth.raw_login_data.get("Version") if auth.raw_login_data else None,
                "ExpiredTime": auth.raw_login_data.get("ExpiredTime") if auth.raw_login_data else None,
            },
            request_params={"phone": auth.phone, "company_code": company_code, "platform": "JyPos"},
        )
    elif auth.source == "session":
        append_capture_payload_safe(
            capture_batch_id,
            source_endpoint="yeusoft.session.bootstrap",
            payload={
                "UserName": auth.user_name,
                "DeptName": auth.dept_name,
                "DeptCode": auth.dept_code,
                "CompanyCode": company_code,
                "JyApiUrl": api_base_url,
            },
            request_params={"source": "session-json", "session_path": str(auth.session_path) if auth.session_path else None},
        )


def run_fetch_mode(
    *,
    reports: list[ReportSpec],
    output_root: Path,
    transport: str,
    access_token: str,
    api_base_url: str | None,
    auth: AuthContext,
    company_code: str,
    capture_batch_id: str | None,
    refreshed: bool,
) -> int:
    run_dir = output_root / now_local().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    meta: dict[str, Any] = {
        "mode": "fetch",
        "auth_source": auth.source,
        "company_code": company_code,
        "dept_code": auth.dept_code,
        "dept_name": auth.dept_name,
        "api_base_url": api_base_url,
        "capture_batch_id": capture_batch_id,
        "token_refreshed": refreshed,
        "reports": [],
    }

    bootstrap_capture_batch(capture_batch_id, auth, company_code, api_base_url)

    try:
        for index, spec in enumerate(reports, start=1):
            url = maybe_override_url(spec, api_base_url)
            auth_headers = build_report_auth_headers(url, access_token)
            status, payload = perform_request(transport, url, spec.payload, auth_headers)
            report_entry = {
                "title": spec.title,
                "source_endpoint": spec.source_endpoint,
                "url": url,
                "status": status,
                "filename": spec.filename,
            }
            meta["reports"].append(report_entry)
            save_json(run_dir / spec.filename, payload)
            if capture_batch_id:
                append_capture_payload_safe(
                    capture_batch_id,
                    source_endpoint=spec.source_endpoint,
                    payload=payload,
                    request_params={
                        "title": spec.title,
                        "url": url,
                        "payload": spec.payload,
                        "report_index": index,
                    },
                    page_no=index,
                )
            print(f"[ok] {spec.title} -> {spec.filename}")

        save_json(run_dir / "_meta.json", meta)
        if capture_batch_id:
            update_capture_batch_safe(capture_batch_id, batch_status="captured", pulled_at=now_local())
        print(
            json.dumps(
                {
                    "ok": True,
                    "mode": "fetch",
                    "capture_batch_id": capture_batch_id,
                    "output_dir": str(run_dir),
                    "report_count": len(meta["reports"]),
                },
                ensure_ascii=False,
            )
        )
        return 0
    except error.HTTPError as exc:
        message = exc.read().decode("utf-8", "ignore")
        if capture_batch_id:
            update_capture_batch_safe(capture_batch_id, batch_status="failed", error_message=message[:1000])
        print(f"[error] HTTP {exc.code}: {message}", file=sys.stderr)
        return 1
    except Exception as exc:
        if capture_batch_id:
            update_capture_batch_safe(capture_batch_id, batch_status="failed", error_message=str(exc)[:1000])
        print(f"[error] {exc}", file=sys.stderr)
        return 1


def run_explore_mode(
    *,
    reports: list[ReportSpec],
    output_root: Path,
    transport: str,
    access_token: str,
    api_base_url: str | None,
    auth: AuthContext,
    company_code: str,
    capture_batch_id: str | None,
    refreshed: bool,
    max_pages: int,
    enum_limit: int,
) -> int:
    run_dir = output_root / now_local().strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)

    bootstrap_capture_batch(capture_batch_id, auth, company_code, api_base_url)

    meta: dict[str, Any] = {
        "mode": "explore",
        "auth_source": auth.source,
        "company_code": company_code,
        "dept_code": auth.dept_code,
        "dept_name": auth.dept_name,
        "api_base_url": api_base_url,
        "capture_batch_id": capture_batch_id,
        "token_refreshed": refreshed,
        "max_pages": max_pages,
        "enum_limit": enum_limit,
        "reports": [],
        "has_failures": False,
    }

    for report_index, spec in enumerate(reports, start=1):
        strategy = get_exploration_strategy(spec.title)
        if strategy is None:
            print(f"[warn] {spec.title} 缺少探索策略，已跳过", file=sys.stderr)
            continue

        url = maybe_override_url(spec, api_base_url)
        auth_headers = build_report_auth_headers(url, access_token)
        cases = build_exploration_cases(
            {"title": spec.title, "payload": spec.payload},
            strategy,
            max_pages=max_pages,
            enum_limit=enum_limit,
        )

        probe_results: list[dict[str, Any]] = []
        for case_index, case in enumerate(cases, start=1):
            result_entry = {
                "case_id": case["case_id"],
                "kind": case["kind"],
                "label": case["label"],
                "probe_context": case["probe_context"],
                "request_payload": case["payload"],
            }
            try:
                status, payload = perform_request(transport, url, case["payload"], auth_headers)
                analysis = analyze_response_payload(payload)
                result_entry.update(
                    {
                        "status": status,
                        "analysis": analysis,
                    }
                )
                if capture_batch_id:
                    append_capture_payload_safe(
                        capture_batch_id,
                        source_endpoint=spec.source_endpoint,
                        payload=payload,
                        request_params={
                            "mode": "explore",
                            "title": spec.title,
                            "url": url,
                            "payload": case["payload"],
                            "report_index": report_index,
                            "case_index": case_index,
                            "case_id": case["case_id"],
                            "label": case["label"],
                        },
                        page_no=case_index,
                    )
            except Exception as exc:  # pragma: no cover - network/runtime failure path
                meta["has_failures"] = True
                result_entry.update(
                    {
                        "status": None,
                        "error": str(exc),
                    }
                )
            probe_results.append(result_entry)

        summary = summarize_exploration_results(strategy, probe_results)
        report_result = {
            "title": spec.title,
            "source_endpoint": spec.source_endpoint,
            "url": url,
            "original_payload": spec.payload,
            "risk_labels": summary["risk_labels"],
            "found_additional_pages": summary["found_additional_pages"],
            "found_distinct_enum_results": summary["found_distinct_enum_results"],
            "recommended_capture_strategy": summary["recommended_capture_strategy"],
            "strategy": {
                "pagination": (
                    {
                        "page_path": strategy.pagination.page_path,
                        "page_size_path": strategy.pagination.page_size_path,
                        "start_page": strategy.pagination.start_page,
                        "paged_size": strategy.pagination.paged_size,
                        "include_zero_size_probe": strategy.pagination.include_zero_size_probe,
                    }
                    if strategy.pagination
                    else None
                ),
                "enum_probes": [
                    {"path": enum_probe.path, "candidates": list(enum_probe.candidates)}
                    for enum_probe in strategy.enum_probes
                ],
                "context_fields": list(strategy.context_fields),
                "combine_enum_with_pagination": strategy.combine_enum_with_pagination,
            },
            "probe_results": probe_results,
            "summary": summary,
        }
        save_json(run_dir / f"{slugify(spec.title)}.exploration.json", report_result)
        meta["reports"].append(
            {
                "title": spec.title,
                "file": f"{slugify(spec.title)}.exploration.json",
                "probe_count": len(probe_results),
                "risk_labels": summary["risk_labels"],
                "recommended_capture_strategy": summary["recommended_capture_strategy"],
                "found_additional_pages": summary["found_additional_pages"],
                "found_distinct_enum_results": summary["found_distinct_enum_results"],
            }
        )
        print(f"[ok] explore {spec.title} -> {slugify(spec.title)}.exploration.json")

    save_json(run_dir / "exploration-meta.json", meta)
    if capture_batch_id:
        batch_status = "captured" if not meta["has_failures"] else "partial"
        update_capture_batch_safe(capture_batch_id, batch_status=batch_status, pulled_at=now_local())
    print(
        json.dumps(
            {
                "ok": not meta["has_failures"],
                "mode": "explore",
                "capture_batch_id": capture_batch_id,
                "output_dir": str(run_dir),
                "report_count": len(meta["reports"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="登录 Yeusoft 并按 report_api_samples.md 批量抓原始报表响应")
    parser.add_argument("--report-doc", default=str(REPORT_DOC_PATH))
    parser.add_argument("--readme", default=str(README_PATH))
    parser.add_argument("--output-dir", default=str(RAW_OUTPUT_ROOT))
    parser.add_argument("--mode", choices=["fetch", "explore"], default="fetch", help="fetch 按样本单次抓取；explore 按策略做分页/枚举探测")
    parser.add_argument("--only", action="append", default=[], help="只抓指定报表标题，可重复传入")
    parser.add_argument("--skip-db", action="store_true", help="只落本地文件，不写 capture 库")
    parser.add_argument("--explore-target", choices=["sales_inventory"], default="sales_inventory", help="explore 模式下要跑的接口范围")
    parser.add_argument("--max-pages", type=int, default=2, help="explore 模式下每个接口最多探测多少个分页页码")
    parser.add_argument("--enum-limit", type=int, default=3, help="explore 模式下每个枚举字段最多探测多少个候选值")
    parser.add_argument("--persist-detection", action="store_true", help="explore 模式下显式开启写 capture 库")
    parser.add_argument(
        "--auth-source",
        choices=["auto", "session", "login"],
        default="auto",
        help="鉴权来源：auto 优先 yeusoft_session.json，login 走登录接口，session 只用导出的浏览器会话",
    )
    parser.add_argument(
        "--session-json",
        default=str(DEFAULT_SESSION_PATH),
        help="浏览器导出的会话 JSON 路径，包含 yis_pc_token",
    )
    parser.add_argument(
        "--transport",
        choices=["curl", "urllib"],
        default="curl",
        help="抓取报表时使用的 HTTP 传输实现，当前 ERP 报表推荐 curl",
    )
    args = parser.parse_args()

    report_doc = Path(args.report_doc)
    readme_path = Path(args.readme)
    output_root = Path(args.output_dir)
    session_path = Path(args.session_json)

    auth = resolve_auth_context(args.auth_source, readme_path, session_path)
    access_token = auth.token
    api_base_url = auth.api_base_url
    company_code = auth.company_code or ""

    refreshed = False
    if auth.refresh_token:
        access_token, refresh_expired_time = refresh_session_access_token(auth)
        auth.token = access_token
        refreshed = True
        if auth.source == "session":
            persist_session_refresh(auth, access_token, refresh_expired_time)

    reports = parse_report_specs(report_doc)
    if args.mode == "explore" and not args.only:
        target_titles = set(get_exploration_target_titles(args.explore_target))
        reports = [report for report in reports if report.title in target_titles]
    if args.only:
        wanted = set(args.only)
        reports = [report for report in reports if report.title in wanted]

    if not reports:
        print("未解析到可抓取的报表接口", file=sys.stderr)
        return 1

    persist_capture = should_persist_capture(
        args.mode,
        skip_db=args.skip_db,
        persist_detection=args.persist_detection,
    )
    source_name = "yeusoft-report-exploration" if args.mode == "explore" else "yeusoft-report-bulk"
    capture_batch_id = try_create_capture_batch(source_name) if persist_capture else None

    if args.mode == "explore":
        return run_explore_mode(
            reports=reports,
            output_root=EXPLORATION_OUTPUT_ROOT,
            transport=args.transport,
            access_token=access_token,
            api_base_url=api_base_url,
            auth=auth,
            company_code=company_code,
            capture_batch_id=capture_batch_id,
            refreshed=refreshed,
            max_pages=max(1, args.max_pages),
            enum_limit=max(1, args.enum_limit),
        )

    return run_fetch_mode(
        reports=reports,
        output_root=output_root,
        transport=args.transport,
        access_token=access_token,
        api_base_url=api_base_url,
        auth=auth,
        company_code=company_code,
        capture_batch_id=capture_batch_id,
        refreshed=refreshed,
    )


if __name__ == "__main__":
    raise SystemExit(main())
