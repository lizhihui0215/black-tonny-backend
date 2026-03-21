from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class DashboardPreset(str, Enum):
    today = "today"
    yesterday = "yesterday"
    last7days = "last7days"
    last30days = "last30days"
    thisMonth = "thisMonth"
    lastMonth = "lastMonth"
    custom = "custom"


class CompareType(str, Enum):
    rate = "rate"
    value = "value"


class CompareDirection(str, Enum):
    up = "up"
    down = "down"
    flat = "flat"


class DateRangeSchema(BaseModel):
    preset: DashboardPreset
    startDate: str
    endDate: str
    compareStartDate: str
    compareEndDate: str


class MetricCardSchema(BaseModel):
    value: float = Field(..., description="主值")
    unit: str = Field(..., description="单位")
    compareType: CompareType = Field(..., description="对比值类型")
    compareValue: Optional[float] = Field(None, description="对比值")
    compareDirection: CompareDirection = Field(..., description="趋势方向")
    subText: str = Field(..., description="副文案")


class DashboardSummarySchema(BaseModel):
    salesAmount: MetricCardSchema
    orderCount: MetricCardSchema
    avgOrderValue: MetricCardSchema
    salesQuantity: MetricCardSchema
    attachRate: MetricCardSchema
    lowStockSkuCount: MetricCardSchema
    sizeBreakStyleCount: MetricCardSchema
    outOfSeasonStockQty: MetricCardSchema


class DashboardSummaryResponse(BaseModel):
    dateRange: DateRangeSchema
    summary: DashboardSummarySchema


DASHBOARD_SUMMARY_RESPONSE_EXAMPLE = {
    "dateRange": {
        "preset": "last7days",
        "startDate": "2026-03-15",
        "endDate": "2026-03-21",
        "compareStartDate": "2026-03-08",
        "compareEndDate": "2026-03-14",
    },
    "summary": {
        "salesAmount": {
            "value": 12860,
            "unit": "CNY",
            "compareType": "rate",
            "compareValue": 12.6,
            "compareDirection": "up",
            "subText": "共 38 单",
        },
        "orderCount": {
            "value": 38,
            "unit": "单",
            "compareType": "rate",
            "compareValue": 8.1,
            "compareDirection": "up",
            "subText": "支付订单",
        },
        "avgOrderValue": {
            "value": 338,
            "unit": "CNY",
            "compareType": "rate",
            "compareValue": 5.4,
            "compareDirection": "up",
            "subText": "平均每单成交金额",
        },
        "salesQuantity": {
            "value": 86,
            "unit": "件",
            "compareType": "rate",
            "compareValue": 10.2,
            "compareDirection": "up",
            "subText": "平均每单 2.3 件",
        },
        "attachRate": {
            "value": 2.3,
            "unit": "件/单",
            "compareType": "value",
            "compareValue": 0.2,
            "compareDirection": "up",
            "subText": "件/单",
        },
        "lowStockSkuCount": {
            "value": 12,
            "unit": "个",
            "compareType": "value",
            "compareValue": 3,
            "compareDirection": "up",
            "subText": "近 7 天新增预警",
        },
        "sizeBreakStyleCount": {
            "value": 8,
            "unit": "款",
            "compareType": "value",
            "compareValue": 2,
            "compareDirection": "up",
            "subText": "近 7 天新增缺码",
        },
        "outOfSeasonStockQty": {
            "value": 126,
            "unit": "件",
            "compareType": "value",
            "compareValue": 18,
            "compareDirection": "down",
            "subText": "较上期减少",
        },
    },
}
