from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query
from app.schemas.common import ApiResponse
from app.schemas.dashboard import (
    DASHBOARD_SUMMARY_SUCCESS_RESPONSE_EXAMPLE,
    DashboardPreset,
    DashboardSummaryResponse,
)
from app.services.runtime import get_dashboard_summary_response


router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)


@router.get(
    "/summary",
    response_model=ApiResponse[DashboardSummaryResponse],
    summary="获取 Dashboard 顶部 8 张卡片",
    responses={
        200: {
            "description": "Dashboard 顶部 8 张 summary 卡片",
            "content": {
                "application/json": {
                    "example": DASHBOARD_SUMMARY_SUCCESS_RESPONSE_EXAMPLE,
                }
            },
        }
    },
)
def get_dashboard_summary(
    preset: DashboardPreset = Query(..., description="日期预设"),
    start_date: date | None = Query(None, description="自定义开始日期"),
    end_date: date | None = Query(None, description="自定义结束日期"),
) -> ApiResponse[DashboardSummaryResponse]:
    try:
        payload = get_dashboard_summary_response(
            preset=preset,
            start_date=start_date,
            end_date=end_date,
        )
        return ApiResponse[DashboardSummaryResponse].success(payload)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Dashboard summary payload not found: {error}") from error
