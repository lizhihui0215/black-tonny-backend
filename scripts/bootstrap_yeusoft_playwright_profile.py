#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.fetch_yeusoft_report_payloads import README_PATH, read_login_auth


SITE_URL = "https://jypos.yeusoft.net/"
DEFAULT_PROFILE_DIR = PROJECT_ROOT / "tmp" / "capture-samples" / "playwright-profile"


def import_playwright():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - runtime guidance only
        raise RuntimeError(
            "当前环境缺少 Python Playwright。请先安装 research 依赖，并执行 `python -m playwright install chromium`。"
        ) from exc
    return sync_playwright


def decode_jwt_payload(token: str | None) -> dict[str, Any]:
    if not token:
        return {}
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload = parts[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8")
        return json.loads(decoded)
    except Exception:
        return {}


def build_local_storage_seed(readme_path: Path) -> dict[str, Any]:
    auth = read_login_auth(readme_path)
    login_data = auth.raw_login_data or {}
    refresh_payload = decode_jwt_payload(auth.refresh_token)
    refresh_expired_time = refresh_payload.get("exp")
    return {
        "yis_pc_token": auth.token,
        "yis_v2_refreshToken": auth.refresh_token or "",
        "yis_pc_logindata": json.dumps(login_data, ensure_ascii=False),
        "yis_pc_comcode": auth.company_code or "",
        "yis_pc_userid": auth.phone or "",
        "yis_pc_userName": auth.user_name or "",
        "yis_pc_company": login_data.get("Company"),
        "yis_pc_DeptCode": auth.dept_code or "",
        "yis_pc_deptName": auth.dept_name or "",
        "yisapiurl": login_data.get("JyApiUrl") or auth.api_base_url or "",
        "YIS_API_ERP_TEMP": login_data.get("JyApiUrl") or auth.api_base_url or "",
        "YIS_API_JY_TEMP": login_data.get("JyApiV2") or "",
        "yis_v2_refreshToken.expiredTime": (int(refresh_expired_time) * 1000) if refresh_expired_time else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="用纯 HTTP 登录链为 Playwright 专用 profile 写入 Yeusoft 登录态。")
    parser.add_argument("--readme", default=str(README_PATH), help="账号说明文件路径")
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR), help="Playwright 持久化 profile 目录")
    parser.add_argument("--site-url", default=SITE_URL, help="Yeusoft 站点地址")
    parser.add_argument("--headless", action="store_true", help="headless 模式启动浏览器写入 profile")
    args = parser.parse_args()

    seed = build_local_storage_seed(Path(args.readme))
    sync_playwright = import_playwright()

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            str(Path(args.profile_dir)),
            headless=args.headless,
            viewport={"width": 1440, "height": 1200},
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(args.site_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            page.evaluate(
                """(seed) => {
                  for (const [key, value] of Object.entries(seed)) {
                    if (value === null || value === undefined) {
                      localStorage.removeItem(key);
                    } else {
                      localStorage.setItem(key, String(value));
                    }
                  }
                }""",
                seed,
            )
            page.reload(wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2500)
            auth_probe = page.evaluate(
                """() => ({
                  apiUrl: localStorage.getItem('yisapiurl') || '',
                  tokenPresent: !!localStorage.getItem('yis_pc_token'),
                  refreshPresent: !!localStorage.getItem('yis_v2_refreshToken'),
                })"""
            )
            print(
                json.dumps(
                    {
                        "ok": True,
                        "profile_dir": str(Path(args.profile_dir)),
                        "site_url": args.site_url,
                        "auth_probe": auth_probe,
                    },
                    ensure_ascii=False,
                )
            )
        finally:
            context.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
