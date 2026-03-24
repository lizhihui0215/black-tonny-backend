from __future__ import annotations

from typing import Any, TypedDict


class SummaryProjectionEndpointSpec(TypedDict):
    description: str
    field_aliases: dict[str, tuple[str, ...]]
    optional_fields: tuple[str, ...]
    required_fields: tuple[str, ...]
    target_table: str


SUMMARY_V0_CAPTURE_SPEC: dict[str, SummaryProjectionEndpointSpec] = {
    "sales_orders": {
        "target_table": "sales_orders",
        "description": "支付订单头数据，支撑销售额、订单数、客单价",
        "required_fields": ("order_id", "paid_at", "paid_amount"),
        "optional_fields": ("store_id", "payment_status", "created_at", "updated_at"),
        "field_aliases": {
            "order_id": ("orderNo", "order_no", "trade_no", "bill_no", "order_sn"),
            "paid_at": ("paidAt", "pay_time", "payTime", "payment_time", "paymentTime", "checkout_time"),
            "paid_amount": (
                "paidAmount",
                "pay_amount",
                "payAmount",
                "actual_amount",
                "actualAmount",
                "real_amount",
                "realAmount",
                "received_amount",
                "receivedAmount",
            ),
            "store_id": ("storeId", "shop_id", "shopId"),
            "payment_status": ("paymentStatus", "pay_status", "payStatus", "status"),
            "created_at": ("createdAt", "create_time", "createTime"),
            "updated_at": ("updatedAt", "update_time", "updateTime"),
        },
    },
    "sales_order_items": {
        "target_table": "sales_order_items",
        "description": "订单商品明细，支撑销售件数和连带率",
        "required_fields": ("order_id", "sku_id", "quantity"),
        "optional_fields": ("style_code", "color_code", "size_code", "created_at", "updated_at"),
        "field_aliases": {
            "order_id": ("orderNo", "order_no", "trade_no", "bill_no"),
            "sku_id": ("skuCode", "sku_code", "skuNo", "sku_no", "item_sku_id"),
            "quantity": ("qty", "num", "count", "sale_qty", "saleQty"),
            "style_code": ("styleCode", "style_code", "spu_code", "spuCode"),
            "color_code": ("colorCode", "color_code"),
            "size_code": ("sizeCode", "size_code"),
            "created_at": ("createdAt", "create_time", "createTime"),
            "updated_at": ("updatedAt", "update_time", "updateTime"),
        },
    },
    "inventory_current": {
        "target_table": "inventory_current",
        "description": "当前库存状态，支撑低库存、缺码、过季库存当前值",
        "required_fields": ("sku_id", "on_hand_qty", "safe_stock_qty"),
        "optional_fields": (
            "store_id",
            "style_code",
            "color_code",
            "size_code",
            "season_tag",
            "is_all_season",
            "is_target_size",
            "is_active_sale",
            "updated_at",
        ),
        "field_aliases": {
            "sku_id": ("skuCode", "sku_code", "skuNo", "sku_no", "item_sku_id"),
            "on_hand_qty": (
                "stock_qty",
                "stockQty",
                "current_stock",
                "currentStock",
                "available_qty",
                "availableQty",
                "inventory_qty",
                "inventoryQty",
            ),
            "safe_stock_qty": (
                "safe_qty",
                "safeQty",
                "warn_stock",
                "warnStock",
                "security_stock",
                "securityStock",
                "alarm_stock",
                "alarmStock",
            ),
            "store_id": ("storeId", "shop_id", "shopId"),
            "style_code": ("styleCode", "style_code", "spu_code", "spuCode"),
            "color_code": ("colorCode", "color_code"),
            "size_code": ("sizeCode", "size_code"),
            "season_tag": ("season", "seasonTag", "season_label", "seasonLabel"),
            "is_all_season": ("allSeason", "all_season", "isAllSeason", "fourSeason", "four_season"),
            "is_target_size": ("targetSize", "target_size", "isTargetSize"),
            "is_active_sale": ("activeSale", "active_sale", "isActiveSale", "onSale", "is_on_sale"),
            "updated_at": ("updatedAt", "update_time", "updateTime"),
        },
    },
    "inventory_daily_snapshot": {
        "target_table": "inventory_daily_snapshot",
        "description": "库存日快照，支撑库存风险类卡片的对比周期变化",
        "required_fields": ("snapshot_date", "sku_id", "on_hand_qty", "safe_stock_qty"),
        "optional_fields": (
            "store_id",
            "style_code",
            "color_code",
            "size_code",
            "season_tag",
            "is_all_season",
            "is_target_size",
            "is_active_sale",
            "created_at",
        ),
        "field_aliases": {
            "snapshot_date": ("snapshotDate", "biz_date", "bizDate", "stat_date", "statDate", "date"),
            "sku_id": ("skuCode", "sku_code", "skuNo", "sku_no", "item_sku_id"),
            "on_hand_qty": (
                "stock_qty",
                "stockQty",
                "current_stock",
                "currentStock",
                "available_qty",
                "availableQty",
                "inventory_qty",
                "inventoryQty",
            ),
            "safe_stock_qty": (
                "safe_qty",
                "safeQty",
                "warn_stock",
                "warnStock",
                "security_stock",
                "securityStock",
                "alarm_stock",
                "alarmStock",
            ),
            "store_id": ("storeId", "shop_id", "shopId"),
            "style_code": ("styleCode", "style_code", "spu_code", "spuCode"),
            "color_code": ("colorCode", "color_code"),
            "size_code": ("sizeCode", "size_code"),
            "season_tag": ("season", "seasonTag", "season_label", "seasonLabel"),
            "is_all_season": ("allSeason", "all_season", "isAllSeason", "fourSeason", "four_season"),
            "is_target_size": ("targetSize", "target_size", "isTargetSize"),
            "is_active_sale": ("activeSale", "active_sale", "isActiveSale", "onSale", "is_on_sale"),
            "created_at": ("createdAt", "create_time", "createTime"),
        },
    },
}


SUMMARY_V0_CAPTURE_ENDPOINTS: tuple[str, ...] = tuple(SUMMARY_V0_CAPTURE_SPEC.keys())


def canonicalize_summary_v0_row(endpoint: str, row: dict[str, Any]) -> dict[str, Any]:
    spec = SUMMARY_V0_CAPTURE_SPEC[endpoint]
    aliases = spec["field_aliases"]
    lowered = {str(key).strip().lower(): value for key, value in row.items()}

    canonical = dict(row)
    for field in spec["required_fields"] + spec["optional_fields"]:
        current_value = canonical.get(field)
        if current_value not in (None, ""):
            continue

        for alias in aliases.get(field, ()):
            if alias in row and row[alias] not in (None, ""):
                canonical[field] = row[alias]
                break

            alias_value = lowered.get(alias.strip().lower())
            if alias_value not in (None, ""):
                canonical[field] = alias_value
                break

    return canonical
