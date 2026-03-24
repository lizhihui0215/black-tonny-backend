"""Boilerplate-aligned capture admission entrypoints.

This package is the preferred import surface for formal capture admission
orchestration during migration. Flat service modules remain for compatibility.
"""

from app.services.customer_capture_admission_service import (
    build_customer_capture_admission_bundle,
    build_customer_capture_research_bundle,
    persist_customer_capture_admission_bundle,
    persist_customer_capture_research_bundle,
)
from app.services.daily_payment_snapshot_capture_admission_service import (
    DAILY_PAYMENT_SNAPSHOT_RECORDS_ENDPOINT,
    build_daily_payment_snapshot_capture_admission_bundle,
    persist_daily_payment_snapshot_capture_admission_bundle,
)
from app.services.inventory_capture_admission_service import (
    build_inventory_capture_admission_bundle,
    build_outin_research_sweep_summary,
    persist_inventory_detail_capture_admission_bundle,
    persist_outin_capture_admission_bundle,
    persist_outin_capture_research_bundle,
)
from app.services.member_capture_admission_service import (
    build_member_capture_admission_bundle,
    build_member_capture_research_bundle,
    persist_member_capture_admission_bundle,
    persist_member_capture_research_bundle,
)
from app.services.member_analysis_snapshot_capture_admission_service import (
    MEMBER_ANALYSIS_SNAPSHOT_RECORDS_ENDPOINT,
    build_member_analysis_snapshot_capture_admission_bundle,
    persist_member_analysis_snapshot_capture_admission_bundle,
)
from app.services.member_sales_rank_snapshot_capture_admission_service import (
    MEMBER_SALES_RANK_SNAPSHOT_RECORDS_ENDPOINT,
    build_member_sales_rank_snapshot_capture_admission_bundle,
    persist_member_sales_rank_snapshot_capture_admission_bundle,
)
from app.services.member_maintenance_capture_admission_service import (
    MEMBER_MAINTENANCE_RECORDS_ENDPOINT,
    build_member_maintenance_capture_admission_bundle,
    build_member_maintenance_capture_research_bundle,
    persist_member_maintenance_capture_admission_bundle,
    persist_member_maintenance_capture_research_bundle,
)
from app.services.product_capture_admission_service import (
    build_product_capture_admission_bundle,
    build_product_capture_research_bundle,
    persist_product_capture_admission_bundle,
    persist_product_capture_research_bundle,
)
from app.services.product_sales_snapshot_capture_admission_service import (
    PRODUCT_SALES_SNAPSHOT_RECORDS_ENDPOINT,
    build_product_sales_snapshot_capture_admission_bundle,
    persist_product_sales_snapshot_capture_admission_bundle,
)
from app.services.receipt_confirmation_capture_admission_service import (
    build_receipt_confirmation_capture_admission_bundle,
    build_receipt_confirmation_capture_research_bundle,
    persist_receipt_confirmation_capture_admission_bundle,
    persist_receipt_confirmation_capture_research_bundle,
)
from app.services.return_detail_capture_admission_service import (
    build_return_detail_capture_research_bundle,
    persist_return_detail_capture_research_bundle,
)
from app.services.sales_capture_admission_service import (
    build_sales_capture_admission_bundle,
    persist_sales_capture_admission_bundle,
)
from app.services.store_stocktaking_capture_admission_service import (
    build_store_stocktaking_capture_admission_bundle,
    build_store_stocktaking_capture_research_bundle,
    persist_store_stocktaking_capture_admission_bundle,
    persist_store_stocktaking_capture_research_bundle,
)
from app.services.store_stocktaking_secondary_capture_service import (
    build_store_stocktaking_diff_capture_research_bundle,
    persist_store_stocktaking_diff_capture_research_bundle,
)
from app.services.stored_value_capture_admission_service import (
    build_stored_value_capture_admission_bundle,
    build_stored_value_capture_research_bundle,
    persist_stored_value_capture_admission_bundle,
    persist_stored_value_capture_research_bundle,
)
from app.services.stored_value_summary_snapshot_capture_admission_service import (
    STORED_VALUE_BY_STORE_SNAPSHOT_RECORDS_ENDPOINT,
    STORED_VALUE_CARD_SUMMARY_SNAPSHOT_RECORDS_ENDPOINT,
    build_stored_value_by_store_snapshot_capture_admission_bundle,
    build_stored_value_card_summary_snapshot_capture_admission_bundle,
    persist_stored_value_by_store_snapshot_capture_admission_bundle,
    persist_stored_value_card_summary_snapshot_capture_admission_bundle,
)

__all__ = [
    "DAILY_PAYMENT_SNAPSHOT_RECORDS_ENDPOINT",
    "MEMBER_ANALYSIS_SNAPSHOT_RECORDS_ENDPOINT",
    "MEMBER_MAINTENANCE_RECORDS_ENDPOINT",
    "MEMBER_SALES_RANK_SNAPSHOT_RECORDS_ENDPOINT",
    "PRODUCT_SALES_SNAPSHOT_RECORDS_ENDPOINT",
    "STORED_VALUE_BY_STORE_SNAPSHOT_RECORDS_ENDPOINT",
    "STORED_VALUE_CARD_SUMMARY_SNAPSHOT_RECORDS_ENDPOINT",
    "build_customer_capture_admission_bundle",
    "build_customer_capture_research_bundle",
    "build_daily_payment_snapshot_capture_admission_bundle",
    "build_inventory_capture_admission_bundle",
    "build_member_capture_admission_bundle",
    "build_member_capture_research_bundle",
    "build_member_analysis_snapshot_capture_admission_bundle",
    "build_member_maintenance_capture_admission_bundle",
    "build_member_maintenance_capture_research_bundle",
    "build_member_sales_rank_snapshot_capture_admission_bundle",
    "build_outin_research_sweep_summary",
    "build_product_capture_admission_bundle",
    "build_product_capture_research_bundle",
    "build_product_sales_snapshot_capture_admission_bundle",
    "build_receipt_confirmation_capture_admission_bundle",
    "build_receipt_confirmation_capture_research_bundle",
    "build_return_detail_capture_research_bundle",
    "build_sales_capture_admission_bundle",
    "build_store_stocktaking_capture_admission_bundle",
    "build_store_stocktaking_capture_research_bundle",
    "build_store_stocktaking_diff_capture_research_bundle",
    "build_stored_value_capture_admission_bundle",
    "build_stored_value_capture_research_bundle",
    "build_stored_value_by_store_snapshot_capture_admission_bundle",
    "build_stored_value_card_summary_snapshot_capture_admission_bundle",
    "persist_customer_capture_admission_bundle",
    "persist_customer_capture_research_bundle",
    "persist_daily_payment_snapshot_capture_admission_bundle",
    "persist_inventory_detail_capture_admission_bundle",
    "persist_member_capture_admission_bundle",
    "persist_member_capture_research_bundle",
    "persist_member_analysis_snapshot_capture_admission_bundle",
    "persist_member_maintenance_capture_admission_bundle",
    "persist_member_maintenance_capture_research_bundle",
    "persist_member_sales_rank_snapshot_capture_admission_bundle",
    "persist_outin_capture_admission_bundle",
    "persist_outin_capture_research_bundle",
    "persist_product_capture_admission_bundle",
    "persist_product_capture_research_bundle",
    "persist_product_sales_snapshot_capture_admission_bundle",
    "persist_receipt_confirmation_capture_admission_bundle",
    "persist_receipt_confirmation_capture_research_bundle",
    "persist_return_detail_capture_research_bundle",
    "persist_sales_capture_admission_bundle",
    "persist_store_stocktaking_capture_admission_bundle",
    "persist_store_stocktaking_capture_research_bundle",
    "persist_store_stocktaking_diff_capture_research_bundle",
    "persist_stored_value_capture_admission_bundle",
    "persist_stored_value_capture_research_bundle",
    "persist_stored_value_by_store_snapshot_capture_admission_bundle",
    "persist_stored_value_card_summary_snapshot_capture_admission_bundle",
]
