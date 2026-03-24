from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, select
from zoneinfo import ZoneInfo

from app.core.config import clear_settings_cache
from app.db.base import (
    analysis_batches,
    capture_batches,
    inventory_current,
    inventory_daily_snapshot,
    sales_order_items,
    sales_orders,
)
from app.db.engine import clear_engine_caches


def _configure_test_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CAPTURE_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'capture.db'}")
    monkeypatch.setenv("SERVING_DB_URL", f"sqlite+pysqlite:///{tmp_path / 'serving.db'}")
    monkeypatch.setenv("PAYLOAD_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("SAMPLE_DATA_DIR", str(Path(__file__).resolve().parents[1] / "data" / "sample"))
    monkeypatch.setenv("ADMIN_API_TOKEN", "test-token")
    monkeypatch.setenv("FRONTEND_AUTH_SECRET", "test-frontend-auth-secret")
    monkeypatch.setenv("OWNER_LOGIN_USERNAME", "owner")
    monkeypatch.setenv("OWNER_LOGIN_PASSWORD", "123456")
    monkeypatch.setenv("OWNER_LOGIN_REAL_NAME", "老板")
    monkeypatch.setenv("OWNER_LOGIN_AVATAR_URL", "https://avatar.vercel.sh/test-owner.svg?text=BT")
    monkeypatch.setenv("OWNER_LOGIN_HOME_PATH", "/dashboard")
    monkeypatch.setenv("FRONTEND_AUTH_ACCESS_TOKEN_TTL_SECONDS", "3600")
    clear_settings_cache()
    clear_engine_caches()


def _login_frontend(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={
            "password": "123456",
            "username": "owner",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0
    access_token = payload["data"]["accessToken"]
    assert isinstance(access_token, str)
    assert access_token
    return {"Authorization": f"Bearer {access_token}"}


def test_health_and_manifest(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.main import app

    with TestClient(app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "API 服务" in root.text
        assert "MySQL" in root.text
        assert "/api/status" in root.text
        assert "/api/manifest" in root.text
        assert "/redoc" in root.text
        health = client.get("/api/health")
        assert health.status_code == 200
        status = client.get("/api/status")
        assert status.status_code == 200
        status_payload = status.json()
        assert status_payload["code"] == 0
        assert status_payload["message"] == "ok"
        status_data = status_payload["data"]
        assert "runtime" in status_data
        assert "components" in status_data
        assert "system" in status_data
        assert "cache_summary" in status_data
        assert "database_summary" in status_data
        assert status_data["runtime"]["hostname"]
        assert status_data["runtime"]["python_version"]
        assert status_data["runtime"]["process_id"] > 0
        assert "disk_total_bytes" in status_data["system"]
        assert "disk_used_bytes" in status_data["system"]
        assert "disk_free_bytes" in status_data["system"]
        assert "load_avg" in status_data["system"]
        assert "serving" in status_data["database_summary"]
        assert "capture" in status_data["database_summary"]
        assert "table_counts" in status_data["database_summary"]["serving"]
        assert "table_counts" in status_data["database_summary"]["capture"]
        assert status_data["components"]["analysis_source"]["status"] == "warning"
        manifest = client.get("/api/manifest")
        assert manifest.status_code == 200
        payload = manifest.json()
        assert payload["code"] == 0
        assert payload["message"] == "ok"
        assert payload["data"]["available_pages"]["dashboard"] == "/api/pages/dashboard"

        page = client.get("/api/pages/dashboard")
        assert page.status_code == 200
        page_payload = page.json()
        assert page_payload["code"] == 0
        assert page_payload["message"] == "ok"
        assert "meta" in page_payload["data"]
        assert "summary_cards" in page_payload["data"]


def test_frontend_auth_contract(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.main import app

    with TestClient(app) as client:
        invalid = client.post(
            "/api/auth/login",
            json={"password": "bad-password", "username": "owner"},
        )
        assert invalid.status_code == 401
        invalid_payload = invalid.json()
        assert invalid_payload["code"] == 40120
        assert invalid_payload["message"] == "Invalid username or password."

        login = client.post(
            "/api/auth/login",
            json={"password": "123456", "username": "owner"},
        )
        assert login.status_code == 200
        login_payload = login.json()
        assert login_payload["code"] == 0
        token = login_payload["data"]["accessToken"]

        headers = {"Authorization": f"Bearer {token}"}
        codes = client.get("/api/auth/codes", headers=headers)
        assert codes.status_code == 200
        assert codes.json()["data"] == ["black-tonny"]

        user_info = client.get("/api/user/info", headers=headers)
        assert user_info.status_code == 200
        user_payload = user_info.json()
        assert user_payload["code"] == 0
        assert user_payload["data"]["userId"] == "black-tonny-owner"
        assert user_payload["data"]["roles"] == ["owner"]
        assert user_payload["data"]["homePath"] == "/dashboard"
        assert user_payload["data"]["token"] == token

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200
        logout_payload = logout.json()
        assert logout_payload["code"] == 0
        assert logout_payload["data"]["success"] is True


def test_rebuild_job_refreshes_cache(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.main import app
    from app.db.engine import get_serving_engine

    with TestClient(app) as client:
        response = client.post(
            "/api/jobs/rebuild",
            headers={"X-Admin-Token": "test-token"},
            json={"sync_mode": "full", "build_only": False},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 0
        job_id = payload["data"]["job_id"]
        detail = client.get(f"/api/jobs/{job_id}")
        assert detail.status_code == 200
        detail_payload = detail.json()
        assert detail_payload["code"] == 0
        assert detail_payload["data"]["status"] in {"queued", "running", "success"}

    with get_serving_engine().begin() as connection:
        row = connection.execute(select(analysis_batches.c.analysis_batch_id)).first()
    assert row is not None


def test_dashboard_summary_contract_and_openapi(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.main import app

    with TestClient(app) as client:
        response = client.get(
            "/api/dashboard/summary",
            params={"preset": "last7days"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 0
        assert payload["message"] == "ok"
        assert payload["data"]["dateRange"]["preset"] == "last7days"
        assert set(payload["data"]["summary"].keys()) == {
            "salesAmount",
            "orderCount",
            "avgOrderValue",
            "salesQuantity",
            "attachRate",
            "lowStockSkuCount",
            "sizeBreakStyleCount",
            "outOfSeasonStockQty",
        }
        assert payload["data"]["summary"]["salesAmount"]["subText"].startswith(
            "共 "
        )
        assert payload["data"]["summary"]["attachRate"]["subText"] == "件/单"
        assert (
            payload["data"]["summary"]["lowStockSkuCount"]["subText"]
            == "近 7 天新增预警"
        )

        start = date.fromisoformat(payload["data"]["dateRange"]["startDate"])
        end = date.fromisoformat(payload["data"]["dateRange"]["endDate"])
        compare_start = date.fromisoformat(
            payload["data"]["dateRange"]["compareStartDate"]
        )
        compare_end = date.fromisoformat(
            payload["data"]["dateRange"]["compareEndDate"]
        )
        assert (end - start).days == (compare_end - compare_start).days

        openapi_payload = client.get("/openapi.json")
        assert openapi_payload.status_code == 200
        assert "/api/dashboard/summary" in openapi_payload.json()["paths"]
        assert "/api/assistant/chat" in openapi_payload.json()["paths"]


def test_assistant_chat_contract(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/assistant/chat",
            json={
                "prompt": "今天先看什么",
                "context": {
                    "pageKey": "dashboard",
                    "pageTitle": "经营总览",
                    "summary": "先看顶部 8 张卡，再决定是否继续下钻。",
                    "metrics": [
                        "销售额 3.2 万，较上期 +12%",
                        "订单数 182，较上期 +8%",
                    ],
                    "actions": [
                        {
                            "title": "先看 summary，再决定是否下钻到趋势和库存模块。",
                            "note": "先用顶部 8 张卡确认结果、效率和库存风险。",
                        },
                        {
                            "title": "切日期时优先看销售类卡片变化，再看库存类副值变化。",
                            "note": "当前页统一跟随日期区间变化。",
                        },
                    ],
                },
                "recentMessages": [
                    {
                        "role": "assistant",
                        "content": "我会基于当前页上下文回答。",
                    }
                ],
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 0
        assert payload["message"] == "ok"
        assert payload["data"]["provider"] == "backend-context"
        assert payload["data"]["grounded"] is True
        assert payload["data"]["reply"].startswith("经营总览这页我建议先按这个顺序推进：")
        assert "先看 summary" in payload["data"]["reply"]


def test_cost_snapshot_contract(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.main import app

    with TestClient(app) as client:
        initial = client.get("/api/cost-snapshot")
        assert initial.status_code == 200
        initial_payload = initial.json()
        assert initial_payload["code"] == 0
        assert initial_payload["data"]["snapshot"] == {}
        assert initial_payload["data"]["history"] == []

        saved = client.post(
            "/api/cost-snapshot",
            headers={"X-Admin-Token": "test-token"},
            json={
                "snapshot": {
                    "snapshot_name": "2026-03 sample",
                    "snapshot_datetime": "2026-03-21T10:00:00+08:00",
                    "rent_amount": 12800,
                }
            },
        )
        assert saved.status_code == 200
        saved_payload = saved.json()
        assert saved_payload["code"] == 0
        assert saved_payload["data"]["snapshot"]["rent_amount"] == 12800
        assert len(saved_payload["data"]["history"]) == 1


def test_dashboard_summary_custom_range_validation(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.main import app

    with TestClient(app) as client:
        missing_custom = client.get(
            "/api/dashboard/summary",
            params={"preset": "custom"},
        )
        assert missing_custom.status_code == 422

        custom = client.get(
            "/api/dashboard/summary",
            params={
                "preset": "custom",
                "start_date": "2026-03-01",
                "end_date": "2026-03-14",
            },
        )
        assert custom.status_code == 200
        payload = custom.json()
        assert payload["code"] == 0
        assert payload["data"]["dateRange"]["startDate"] == "2026-03-01"
        assert payload["data"]["dateRange"]["endDate"] == "2026-03-14"
        assert (
            payload["data"]["summary"]["sizeBreakStyleCount"]["subText"]
            == "所选区间新增缺码"
        )


def test_dashboard_summary_prefers_serving_database(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_serving_engine, init_databases
    from app.main import app
    from app.services.runtime import dashboard as runtime_dashboard

    frozen_now = datetime(2026, 3, 21, 10, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    monkeypatch.setattr(runtime_dashboard, "now_local", lambda: frozen_now)
    init_databases()

    with get_serving_engine().begin() as connection:
        connection.execute(
            insert(analysis_batches).values(
                analysis_batch_id="analysis-001",
                capture_batch_id="capture-001",
                batch_status="success",
                source_endpoint="dashboard-summary-test",
                pulled_at=frozen_now,
                transformed_at=frozen_now,
                created_at=frozen_now,
                updated_at=frozen_now,
            )
        )
        connection.execute(
            insert(sales_orders),
            [
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "store_id": "store-001",
                    "order_id": "order-current-1",
                    "paid_at": datetime(2026, 3, 20, 12, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                    "paid_amount": 100,
                    "payment_status": "paid",
                    "created_at": frozen_now,
                    "updated_at": frozen_now,
                },
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "store_id": "store-001",
                    "order_id": "order-current-2",
                    "paid_at": datetime(2026, 3, 21, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                    "paid_amount": 200,
                    "payment_status": "paid",
                    "created_at": frozen_now,
                    "updated_at": frozen_now,
                },
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "store_id": "store-001",
                    "order_id": "order-compare-1",
                    "paid_at": datetime(2026, 3, 10, 11, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                    "paid_amount": 100,
                    "payment_status": "paid",
                    "created_at": frozen_now,
                    "updated_at": frozen_now,
                },
            ],
        )
        connection.execute(
            insert(sales_order_items),
            [
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "order_id": "order-current-1",
                    "sku_id": "sku-a-90",
                    "style_code": "style-a",
                    "color_code": "red",
                    "size_code": "90",
                    "quantity": 2,
                    "created_at": frozen_now,
                    "updated_at": frozen_now,
                },
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "order_id": "order-current-2",
                    "sku_id": "sku-b-100",
                    "style_code": "style-b",
                    "color_code": "blue",
                    "size_code": "100",
                    "quantity": 1,
                    "created_at": frozen_now,
                    "updated_at": frozen_now,
                },
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "order_id": "order-compare-1",
                    "sku_id": "sku-c-90",
                    "style_code": "style-c",
                    "color_code": "pink",
                    "size_code": "90",
                    "quantity": 1,
                    "created_at": frozen_now,
                    "updated_at": frozen_now,
                },
            ],
        )
        connection.execute(
            insert(inventory_current),
            [
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "store_id": "store-001",
                    "sku_id": "sku-a-90",
                    "style_code": "style-a",
                    "color_code": "red",
                    "size_code": "90",
                    "on_hand_qty": 0,
                    "safe_stock_qty": 2,
                    "season_tag": "春夏",
                    "is_all_season": False,
                    "is_target_size": True,
                    "is_active_sale": True,
                    "updated_at": frozen_now,
                },
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "store_id": "store-001",
                    "sku_id": "sku-a-100",
                    "style_code": "style-a",
                    "color_code": "red",
                    "size_code": "100",
                    "on_hand_qty": 3,
                    "safe_stock_qty": 2,
                    "season_tag": "春夏",
                    "is_all_season": False,
                    "is_target_size": True,
                    "is_active_sale": True,
                    "updated_at": frozen_now,
                },
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "store_id": "store-001",
                    "sku_id": "sku-b-90",
                    "style_code": "style-b",
                    "color_code": "blue",
                    "size_code": "90",
                    "on_hand_qty": 1,
                    "safe_stock_qty": 1,
                    "season_tag": "秋冬",
                    "is_all_season": False,
                    "is_target_size": True,
                    "is_active_sale": True,
                    "updated_at": frozen_now,
                },
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "store_id": "store-001",
                    "sku_id": "sku-c-100",
                    "style_code": "style-c",
                    "color_code": "green",
                    "size_code": "100",
                    "on_hand_qty": 5,
                    "safe_stock_qty": 2,
                    "season_tag": "秋冬",
                    "is_all_season": False,
                    "is_target_size": True,
                    "is_active_sale": True,
                    "updated_at": frozen_now,
                },
            ],
        )
        connection.execute(
            insert(inventory_daily_snapshot),
            [
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "snapshot_date": date(2026, 3, 14),
                    "store_id": "store-001",
                    "sku_id": "sku-a-90",
                    "style_code": "style-a",
                    "color_code": "red",
                    "size_code": "90",
                    "on_hand_qty": 2,
                    "safe_stock_qty": 2,
                    "season_tag": "春夏",
                    "is_all_season": False,
                    "is_target_size": True,
                    "is_active_sale": True,
                    "created_at": frozen_now,
                },
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "snapshot_date": date(2026, 3, 14),
                    "store_id": "store-001",
                    "sku_id": "sku-a-100",
                    "style_code": "style-a",
                    "color_code": "red",
                    "size_code": "100",
                    "on_hand_qty": 3,
                    "safe_stock_qty": 2,
                    "season_tag": "春夏",
                    "is_all_season": False,
                    "is_target_size": True,
                    "is_active_sale": True,
                    "created_at": frozen_now,
                },
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "snapshot_date": date(2026, 3, 14),
                    "store_id": "store-001",
                    "sku_id": "sku-b-90",
                    "style_code": "style-b",
                    "color_code": "blue",
                    "size_code": "90",
                    "on_hand_qty": 0,
                    "safe_stock_qty": 1,
                    "season_tag": "秋冬",
                    "is_all_season": False,
                    "is_target_size": True,
                    "is_active_sale": True,
                    "created_at": frozen_now,
                },
                {
                    "analysis_batch_id": "analysis-001",
                    "capture_batch_id": "capture-001",
                    "snapshot_date": date(2026, 3, 14),
                    "store_id": "store-001",
                    "sku_id": "sku-c-100",
                    "style_code": "style-c",
                    "color_code": "green",
                    "size_code": "100",
                    "on_hand_qty": 7,
                    "safe_stock_qty": 2,
                    "season_tag": "秋冬",
                    "is_all_season": False,
                    "is_target_size": True,
                    "is_active_sale": True,
                    "created_at": frozen_now,
                },
            ],
        )

    with TestClient(app) as client:
        auth_headers = _login_frontend(client)
        response = client.get(
            "/api/dashboard/summary",
            params={"preset": "last7days"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["code"] == 0
        assert payload["data"]["summary"]["salesAmount"]["value"] == 300
        assert payload["data"]["summary"]["salesAmount"]["compareValue"] == 200
        assert payload["data"]["summary"]["orderCount"]["value"] == 2
        assert payload["data"]["summary"]["avgOrderValue"]["value"] == 150
        assert payload["data"]["summary"]["salesQuantity"]["value"] == 3
        assert payload["data"]["summary"]["attachRate"]["value"] == 1.5
        assert payload["data"]["summary"]["attachRate"]["compareValue"] == 0.5
        assert payload["data"]["summary"]["lowStockSkuCount"]["value"] == 2
        assert (
            payload["data"]["summary"]["lowStockSkuCount"]["compareDirection"]
            == "flat"
        )
        assert payload["data"]["summary"]["sizeBreakStyleCount"]["value"] == 1
        assert payload["data"]["summary"]["outOfSeasonStockQty"]["value"] == 6
        assert (
            payload["data"]["summary"]["outOfSeasonStockQty"]["compareValue"]
            == -1
        )
        assert (
            payload["data"]["summary"]["outOfSeasonStockQty"]["subText"]
            == "较上期减少"
        )


def test_transform_capture_batch_to_serving(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_capture_engine, get_serving_engine, init_databases
    from app.services.batch_service import append_capture_payload, create_capture_batch
    from app.services.serving import transform_capture_batch_to_serving

    init_databases()
    capture_batch_id = create_capture_batch(source_name="summary-test", capture_batch_id="capture-raw-001")

    append_capture_payload(
        capture_batch_id,
        source_endpoint="sales_orders",
        payload=[
            {
                "store_id": "store-001",
                "order_id": "order-001",
                "paid_at": "2026-03-20T12:00:00+08:00",
                "paid_amount": 168,
                "payment_status": "paid",
            }
        ],
    )
    append_capture_payload(
        capture_batch_id,
        source_endpoint="sales_order_items",
        payload=[
            {
                "order_id": "order-001",
                "sku_id": "sku-001",
                "style_code": "style-001",
                "color_code": "pink",
                "size_code": "100",
                "quantity": 2,
            }
        ],
    )
    append_capture_payload(
        capture_batch_id,
        source_endpoint="inventory_current",
        payload=[
            {
                "store_id": "store-001",
                "sku_id": "sku-001",
                "style_code": "style-001",
                "color_code": "pink",
                "size_code": "100",
                "on_hand_qty": 1,
                "safe_stock_qty": 2,
                "season_tag": "春夏",
                "is_all_season": False,
                "is_target_size": True,
                "is_active_sale": True,
            }
        ],
    )
    append_capture_payload(
        capture_batch_id,
        source_endpoint="inventory_daily_snapshot",
        payload=[
            {
                "snapshot_date": "2026-03-14",
                "store_id": "store-001",
                "sku_id": "sku-001",
                "style_code": "style-001",
                "color_code": "pink",
                "size_code": "100",
                "on_hand_qty": 3,
                "safe_stock_qty": 2,
                "season_tag": "春夏",
                "is_all_season": False,
                "is_target_size": True,
                "is_active_sale": True,
            }
        ],
    )

    analysis_batch_id = transform_capture_batch_to_serving(
        capture_batch_id,
        analysis_batch_id="analysis-raw-001",
    )
    assert analysis_batch_id == "analysis-raw-001"

    with get_serving_engine().begin() as connection:
        analysis_row = connection.execute(
            select(analysis_batches).where(analysis_batches.c.analysis_batch_id == analysis_batch_id)
        ).mappings().first()
        order_rows = connection.execute(
            select(sales_orders).where(sales_orders.c.analysis_batch_id == analysis_batch_id)
        ).mappings().all()
        item_rows = connection.execute(
            select(sales_order_items).where(sales_order_items.c.analysis_batch_id == analysis_batch_id)
        ).mappings().all()
        inventory_rows = connection.execute(
            select(inventory_current).where(inventory_current.c.analysis_batch_id == analysis_batch_id)
        ).mappings().all()
        snapshot_rows = connection.execute(
            select(inventory_daily_snapshot).where(
                inventory_daily_snapshot.c.analysis_batch_id == analysis_batch_id
            )
        ).mappings().all()

    assert analysis_row is not None
    assert analysis_row["capture_batch_id"] == capture_batch_id
    assert analysis_row["batch_status"] == "success"
    assert len(order_rows) == 1
    assert len(item_rows) == 1
    assert len(inventory_rows) == 1
    assert len(snapshot_rows) == 1

    with get_capture_engine().begin() as connection:
        capture_row = connection.execute(
            select(capture_batches).where(capture_batches.c.capture_batch_id == capture_batch_id)
        ).mappings().first()

    assert capture_row is not None
    assert capture_row["batch_status"] == "transformed"
    assert capture_row["transformed_at"] is not None


def test_transform_capture_batch_requires_all_summary_endpoints(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import init_databases
    from app.services.batch_service import append_capture_payload, create_capture_batch
    from app.services.serving import transform_capture_batch_to_serving

    init_databases()
    capture_batch_id = create_capture_batch(source_name="summary-test", capture_batch_id="capture-missing-001")
    append_capture_payload(
        capture_batch_id,
        source_endpoint="sales_orders",
        payload=[
            {
                "order_id": "order-001",
                "paid_at": "2026-03-20T12:00:00+08:00",
                "paid_amount": 168,
            }
        ],
    )

    with pytest.raises(ValueError, match="缺少必要 endpoint"):
        transform_capture_batch_to_serving(capture_batch_id)


def test_transform_capture_batch_supports_common_field_aliases(monkeypatch, tmp_path: Path):
    _configure_test_env(monkeypatch, tmp_path)
    from app.db.engine import get_serving_engine, init_databases
    from app.services.batch_service import append_capture_payload, create_capture_batch
    from app.services.serving import transform_capture_batch_to_serving

    init_databases()
    capture_batch_id = create_capture_batch(source_name="summary-test", capture_batch_id="capture-alias-001")

    append_capture_payload(
        capture_batch_id,
        source_endpoint="sales_orders",
        payload=[
            {
                "shopId": "store-001",
                "orderNo": "order-001",
                "pay_time": "2026-03-20T12:00:00+08:00",
                "actual_amount": 168,
                "status": "paid",
            }
        ],
    )
    append_capture_payload(
        capture_batch_id,
        source_endpoint="sales_order_items",
        payload=[
            {
                "orderNo": "order-001",
                "skuCode": "sku-001",
                "styleCode": "style-001",
                "colorCode": "pink",
                "sizeCode": "100",
                "qty": 2,
            }
        ],
    )
    append_capture_payload(
        capture_batch_id,
        source_endpoint="inventory_current",
        payload=[
            {
                "shopId": "store-001",
                "skuCode": "sku-001",
                "styleCode": "style-001",
                "colorCode": "pink",
                "sizeCode": "100",
                "stockQty": 1,
                "alarmStock": 2,
                "season": "春夏",
                "allSeason": False,
                "targetSize": True,
                "onSale": True,
            }
        ],
    )
    append_capture_payload(
        capture_batch_id,
        source_endpoint="inventory_daily_snapshot",
        payload=[
            {
                "bizDate": "2026-03-14",
                "shopId": "store-001",
                "skuCode": "sku-001",
                "styleCode": "style-001",
                "colorCode": "pink",
                "sizeCode": "100",
                "stockQty": 3,
                "alarmStock": 2,
                "season": "春夏",
                "allSeason": False,
                "targetSize": True,
                "onSale": True,
            }
        ],
    )

    analysis_batch_id = transform_capture_batch_to_serving(capture_batch_id)

    with get_serving_engine().begin() as connection:
        order_row = connection.execute(
            select(sales_orders).where(sales_orders.c.analysis_batch_id == analysis_batch_id)
        ).mappings().first()
        item_row = connection.execute(
            select(sales_order_items).where(sales_order_items.c.analysis_batch_id == analysis_batch_id)
        ).mappings().first()
        inventory_row = connection.execute(
            select(inventory_current).where(inventory_current.c.analysis_batch_id == analysis_batch_id)
        ).mappings().first()
        snapshot_row = connection.execute(
            select(inventory_daily_snapshot).where(
                inventory_daily_snapshot.c.analysis_batch_id == analysis_batch_id
            )
        ).mappings().first()

    assert order_row is not None
    assert order_row["order_id"] == "order-001"
    assert order_row["paid_amount"] == 168
    assert item_row is not None
    assert item_row["sku_id"] == "sku-001"
    assert item_row["quantity"] == 2
    assert inventory_row is not None
    assert inventory_row["safe_stock_qty"] == 2
    assert inventory_row["on_hand_qty"] == 1
    assert snapshot_row is not None
    assert str(snapshot_row["snapshot_date"]) == "2026-03-14"
