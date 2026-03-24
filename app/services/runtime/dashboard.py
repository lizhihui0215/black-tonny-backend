from __future__ import annotations

import copy
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.timezone import now_local
from app.crud import (
    fetch_dashboard_summary_source_rows,
    fetch_latest_analysis_batch_id,
)
from app.schemas.dashboard import (
    CompareDirection,
    DashboardPreset,
    DashboardSummaryResponse,
    DateRangeSchema,
)


SUMMARY_FILENAME = "dashboard_summary.json"
TIME_ACCUMULATING_KEYS = (
    "salesAmount",
    "orderCount",
    "avgOrderValue",
    "salesQuantity",
    "attachRate",
)
CURRENT_STATE_KEYS = (
    "lowStockSkuCount",
    "sizeBreakStyleCount",
    "outOfSeasonStockQty",
)
PERIOD_LABELS: dict[DashboardPreset, str] = {
    DashboardPreset.today: "今日",
    DashboardPreset.yesterday: "昨日",
    DashboardPreset.last7days: "近 7 天",
    DashboardPreset.last30days: "近 30 天",
    DashboardPreset.thisMonth: "本月",
    DashboardPreset.lastMonth: "上月",
    DashboardPreset.custom: "所选区间",
}


def _summary_path(base_dir: Path) -> Path:
    return base_dir / SUMMARY_FILENAME


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_summary_source() -> Path:
    settings = get_settings()
    cache_path = _summary_path(settings.payload_cache_path)
    if cache_path.exists():
        return cache_path
    return _summary_path(settings.sample_data_path)


def _compute_compare_range(start_date: date, end_date: date) -> tuple[date, date]:
    day_count = (end_date - start_date).days + 1
    compare_end = start_date - timedelta(days=1)
    compare_start = compare_end - timedelta(days=day_count - 1)
    return compare_start, compare_end


def _month_start(target: date) -> date:
    return target.replace(day=1)


def _last_month_range(today: date) -> tuple[date, date]:
    first_day_this_month = _month_start(today)
    last_day_previous_month = first_day_this_month - timedelta(days=1)
    return _month_start(last_day_previous_month), last_day_previous_month


def build_dashboard_date_range(
    preset: DashboardPreset,
    start_date: date | None = None,
    end_date: date | None = None,
) -> DateRangeSchema:
    today = now_local().date()

    if preset == DashboardPreset.today:
        range_start = today
        range_end = today
    elif preset == DashboardPreset.yesterday:
        range_start = today - timedelta(days=1)
        range_end = range_start
    elif preset == DashboardPreset.last7days:
        range_start = today - timedelta(days=6)
        range_end = today
    elif preset == DashboardPreset.last30days:
        range_start = today - timedelta(days=29)
        range_end = today
    elif preset == DashboardPreset.thisMonth:
        range_start = _month_start(today)
        range_end = today
    elif preset == DashboardPreset.lastMonth:
        range_start, range_end = _last_month_range(today)
    elif preset == DashboardPreset.custom:
        if start_date is None or end_date is None:
            raise ValueError("preset=custom 时，start_date 和 end_date 都必须传入")
        range_start = start_date
        range_end = end_date
    else:
        raise ValueError(f"不支持的 preset: {preset}")

    if range_start > range_end:
        raise ValueError("start_date 不能晚于 end_date")

    compare_start, compare_end = _compute_compare_range(range_start, range_end)
    return DateRangeSchema(
        preset=preset,
        startDate=range_start.isoformat(),
        endDate=range_end.isoformat(),
        compareStartDate=compare_start.isoformat(),
        compareEndDate=compare_end.isoformat(),
    )


def _baseline_day_count(sample_payload: dict[str, Any]) -> int:
    sample_date_range = sample_payload.get("dateRange") or {}
    start = date.fromisoformat(sample_date_range["startDate"])
    end = date.fromisoformat(sample_date_range["endDate"])
    return (end - start).days + 1


def _round_number(value: float, digits: int = 1) -> float:
    return round(value, digits)


def _rescale_time_accumulating_metrics(
    summary: dict[str, Any],
    target_day_count: int,
    baseline_day_count: int,
) -> None:
    if baseline_day_count <= 0:
        return

    factor = target_day_count / baseline_day_count

    sales_amount = round(float(summary["salesAmount"]["value"]) * factor)
    order_count = round(float(summary["orderCount"]["value"]) * factor)
    sales_quantity = round(float(summary["salesQuantity"]["value"]) * factor)

    avg_order_value = sales_amount / order_count if order_count else 0
    attach_rate = sales_quantity / order_count if order_count else 0

    summary["salesAmount"]["value"] = float(sales_amount)
    summary["salesAmount"]["subText"] = f"共 {order_count} 单"
    summary["orderCount"]["value"] = float(order_count)
    summary["avgOrderValue"]["value"] = _round_number(avg_order_value, 1)
    summary["salesQuantity"]["value"] = float(sales_quantity)
    summary["salesQuantity"]["subText"] = f"平均每单 {attach_rate:.1f} 件"
    summary["attachRate"]["value"] = _round_number(attach_rate, 1)


def _rescale_current_state_compare_values(
    summary: dict[str, Any],
    target_day_count: int,
    baseline_day_count: int,
) -> None:
    if baseline_day_count <= 0:
        return

    factor = target_day_count / baseline_day_count
    for key in ("lowStockSkuCount", "sizeBreakStyleCount", "outOfSeasonStockQty"):
        compare_value = summary[key].get("compareValue")
        if compare_value is None:
            continue
        scaled_value = round(float(compare_value) * factor)
        summary[key]["compareValue"] = None if scaled_value == 0 else float(scaled_value)


def _normalize_compare_direction(metric: dict[str, Any]) -> None:
    compare_value = metric.get("compareValue")
    if compare_value in (None, 0, 0.0):
        metric["compareDirection"] = CompareDirection.flat.value
        metric["compareValue"] = None if compare_value is None else float(compare_value)


def _refresh_subtext(summary: dict[str, Any], preset: DashboardPreset) -> None:
    label = PERIOD_LABELS[preset]
    summary["lowStockSkuCount"]["subText"] = f"{label}新增预警"
    summary["sizeBreakStyleCount"]["subText"] = f"{label}新增缺码"

    out_of_season_direction = summary["outOfSeasonStockQty"]["compareDirection"]
    if out_of_season_direction == CompareDirection.up.value:
        summary["outOfSeasonStockQty"]["subText"] = "较上期增加"
    elif out_of_season_direction == CompareDirection.down.value:
        summary["outOfSeasonStockQty"]["subText"] = "较上期减少"
    else:
        summary["outOfSeasonStockQty"]["subText"] = "较上期持平"


def _load_summary_template() -> dict[str, Any]:
    source_path = _resolve_summary_source()
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    return _load_json(source_path)


def _safe_float(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _coerce_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        token = value.strip().split("T", 1)[0].split(" ", 1)[0]
        return date.fromisoformat(token)
    raise TypeError(f"无法解析日期值: {value!r}")


def _current_season_tag(anchor: date) -> str:
    return "spring_summer" if 3 <= anchor.month <= 8 else "autumn_winter"


def _normalize_season_tag(value: Any) -> str | None:
    if value is None:
        return None

    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    if not normalized:
        return None

    if normalized in {"四季", "四季常规", "all", "all_season", "allseason"}:
        return "all_season"
    if normalized in {"春夏", "spring_summer", "springsummer", "ss"}:
        return "spring_summer"
    if normalized in {"秋冬", "autumn_winter", "autumnwinter", "aw", "fw", "fall_winter"}:
        return "autumn_winter"
    return None


def _metric_direction(delta: float | None) -> str:
    if delta is None or abs(delta) < 1e-9:
        return CompareDirection.flat.value
    return CompareDirection.up.value if delta > 0 else CompareDirection.down.value


def _build_rate_metric(value: float, previous_value: float, unit: str, sub_text: str) -> dict[str, Any]:
    compare_value: float | None
    if previous_value == 0:
        compare_value = None
    else:
        compare_value = _round_number(((value - previous_value) / previous_value) * 100, 1)

    return {
        "value": float(_round_number(value, 1 if unit == "件/单" else 0)),
        "unit": unit,
        "compareType": "rate",
        "compareValue": compare_value,
        "compareDirection": _metric_direction(None if compare_value is None else value - previous_value),
        "subText": sub_text,
    }


def _build_value_metric(value: float, previous_value: float | None, unit: str, sub_text: str) -> dict[str, Any]:
    compare_value = None if previous_value is None else _round_number(value - previous_value, 1)
    return {
        "value": float(_round_number(value, 1 if unit == "件/单" else 0)),
        "unit": unit,
        "compareType": "value",
        "compareValue": compare_value,
        "compareDirection": _metric_direction(compare_value),
        "subText": sub_text,
    }


def _count_low_stock(rows: list[dict[str, Any]]) -> float:
    return float(sum(1 for row in rows if _safe_float(row.get("on_hand_qty")) <= _safe_float(row.get("safe_stock_qty"))))


def _count_size_break_styles(rows: list[dict[str, Any]]) -> float:
    grouped: dict[tuple[str, str], bool] = defaultdict(bool)
    for row in rows:
        if not _safe_bool(row.get("is_target_size")) or not _safe_bool(row.get("is_active_sale")):
            continue
        style_code = str(row.get("style_code") or row.get("sku_id") or "unknown")
        color_code = str(row.get("color_code") or "")
        if _safe_float(row.get("on_hand_qty")) <= 0:
            grouped[(style_code, color_code)] = True
        else:
            grouped.setdefault((style_code, color_code), False)
    return float(sum(1 for missing in grouped.values() if missing))


def _count_out_of_season_qty(rows: list[dict[str, Any]], current_season: str) -> float:
    total = 0.0
    for row in rows:
        if _safe_float(row.get("on_hand_qty")) <= 0:
            continue
        if _safe_bool(row.get("is_all_season")):
            continue
        season_tag = _normalize_season_tag(row.get("season_tag"))
        if season_tag is None or season_tag == current_season:
            continue
        total += _safe_float(row.get("on_hand_qty"))
    return float(_round_number(total, 1))


def _build_summary_from_serving(date_range: DateRangeSchema) -> dict[str, Any] | None:
    try:
        analysis_batch_id = fetch_latest_analysis_batch_id()
        if not analysis_batch_id:
            return None

        source_rows = fetch_dashboard_summary_source_rows(
            analysis_batch_id,
            compare_snapshot_date=date.fromisoformat(date_range.compareEndDate),
        )
        sales_rows = source_rows["sales_rows"]
        inventory_rows = source_rows["inventory_rows"]
        compare_snapshot_rows = source_rows["compare_snapshot_rows"]
        item_rows = source_rows["item_rows"]

        if not sales_rows and not inventory_rows:
            return None

        current_start = date.fromisoformat(date_range.startDate)
        current_end = date.fromisoformat(date_range.endDate)
        compare_start = date.fromisoformat(date_range.compareStartDate)
        compare_end = date.fromisoformat(date_range.compareEndDate)

        paid_orders = [
            row
            for row in sales_rows
            if str(row.get("payment_status") or "paid") == "paid"
        ]
        current_orders = [
            row
            for row in paid_orders
            if current_start <= _coerce_date(row.get("paid_at")) <= current_end
        ]
        previous_orders = [
            row
            for row in paid_orders
            if compare_start <= _coerce_date(row.get("paid_at")) <= compare_end
        ]

        current_order_ids = {str(row.get("order_id")) for row in current_orders}
        previous_order_ids = {str(row.get("order_id")) for row in previous_orders}
        relevant_order_ids = current_order_ids | previous_order_ids

        current_quantity = 0.0
        previous_quantity = 0.0
        if relevant_order_ids:
            for row in item_rows:
                order_id = str(row.get("order_id"))
                if order_id in current_order_ids:
                    current_quantity += _safe_float(row.get("quantity"))
                if order_id in previous_order_ids:
                    previous_quantity += _safe_float(row.get("quantity"))

        current_sales_amount = sum(_safe_float(row.get("paid_amount")) for row in current_orders)
        previous_sales_amount = sum(_safe_float(row.get("paid_amount")) for row in previous_orders)
        current_order_count = float(len(current_order_ids))
        previous_order_count = float(len(previous_order_ids))
        current_avg_order_value = current_sales_amount / current_order_count if current_order_count else 0.0
        previous_avg_order_value = previous_sales_amount / previous_order_count if previous_order_count else 0.0
        current_attach_rate = current_quantity / current_order_count if current_order_count else 0.0
        previous_attach_rate = previous_quantity / previous_order_count if previous_order_count else 0.0

        current_season = _current_season_tag(now_local().date())
        current_low_stock = _count_low_stock(inventory_rows)
        previous_low_stock = (
            _count_low_stock(compare_snapshot_rows) if compare_snapshot_rows else None
        )
        current_size_break = _count_size_break_styles(inventory_rows)
        previous_size_break = (
            _count_size_break_styles(compare_snapshot_rows) if compare_snapshot_rows else None
        )
        current_out_of_season = _count_out_of_season_qty(inventory_rows, current_season)
        previous_out_of_season = (
            _count_out_of_season_qty(compare_snapshot_rows, current_season)
            if compare_snapshot_rows
            else None
        )

        return {
            "salesAmount": _build_rate_metric(
                current_sales_amount,
                previous_sales_amount,
                "CNY",
                f"共 {int(current_order_count)} 单",
            ),
            "orderCount": _build_rate_metric(
                current_order_count,
                previous_order_count,
                "单",
                "支付订单",
            ),
            "avgOrderValue": _build_rate_metric(
                current_avg_order_value,
                previous_avg_order_value,
                "CNY",
                "平均每单成交金额",
            ),
            "salesQuantity": _build_rate_metric(
                current_quantity,
                previous_quantity,
                "件",
                f"平均每单 {current_attach_rate:.1f} 件",
            ),
            "attachRate": _build_value_metric(
                current_attach_rate,
                previous_attach_rate if previous_order_count else None,
                "件/单",
                "件/单",
            ),
            "lowStockSkuCount": _build_value_metric(
                current_low_stock,
                previous_low_stock,
                "个",
                "",
            ),
            "sizeBreakStyleCount": _build_value_metric(
                current_size_break,
                previous_size_break,
                "款",
                "",
            ),
            "outOfSeasonStockQty": _build_value_metric(
                current_out_of_season,
                previous_out_of_season,
                "件",
                "",
            ),
        }
    except SQLAlchemyError:
        return None


def _build_summary_from_sample(
    preset: DashboardPreset,
    date_range: DateRangeSchema,
) -> dict[str, Any]:
    sample_payload = _load_summary_template()
    summary = copy.deepcopy(sample_payload.get("summary") or {})

    target_day_count = (
        date.fromisoformat(date_range.endDate) - date.fromisoformat(date_range.startDate)
    ).days + 1
    baseline_day_count = _baseline_day_count(sample_payload)

    _rescale_time_accumulating_metrics(summary, target_day_count, baseline_day_count)
    _rescale_current_state_compare_values(summary, target_day_count, baseline_day_count)

    for key in TIME_ACCUMULATING_KEYS + CURRENT_STATE_KEYS:
        _normalize_compare_direction(summary[key])

    _refresh_subtext(summary, preset)
    return summary


def get_dashboard_summary_response(
    preset: DashboardPreset,
    start_date: date | None = None,
    end_date: date | None = None,
) -> DashboardSummaryResponse:
    """Boilerplate-aligned runtime implementation for dashboard summary reads."""
    date_range = build_dashboard_date_range(preset, start_date=start_date, end_date=end_date)
    summary = _build_summary_from_serving(date_range) or _build_summary_from_sample(
        preset,
        date_range,
    )
    _refresh_subtext(summary, preset)

    return DashboardSummaryResponse.model_validate(
        {
            "dateRange": date_range.model_dump(),
            "summary": summary,
        }
    )
