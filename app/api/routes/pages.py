from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.page import PagePayloadResponse
from app.services.payload_service import get_page_payload


router = APIRouter(tags=["pages"])


@router.get("/pages/{page_key}", response_model=PagePayloadResponse)
def read_page(page_key: str) -> PagePayloadResponse:
    try:
        payload = get_page_payload(page_key)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Unknown page key: {page_key}") from error
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=f"Payload not found: {page_key}") from error
    return PagePayloadResponse.model_validate(payload)

