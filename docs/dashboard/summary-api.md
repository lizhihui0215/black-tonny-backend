# Dashboard Summary API 文档

> 本文件只定义接口契约。
> 指标业务口径与交互规则以前端 [overview.md（workspace 链接）](../../../black-tonny-frontend/docs/dashboard/overview.md)、[summary-metrics.md（workspace 链接）](../../../black-tonny-frontend/docs/dashboard/summary-metrics.md)、[interaction-rules.md（workspace 链接）](../../../black-tonny-frontend/docs/dashboard/interaction-rules.md)、[summary-analysis-logic.md（workspace 链接）](../../../black-tonny-frontend/docs/dashboard/summary-analysis-logic.md) 为准。

## 1. Endpoint

`GET /api/dashboard/summary`

---

## 2. 接口用途

返回 Dashboard 顶部 8 张 Summary 卡片数据。

---

## 3. Query Parameters

| 参数 | 类型 | 必填 | 说明 |
|---|---|---:|---|
| `preset` | string | 是 | 日期预设：`today` / `yesterday` / `last7days` / `last30days` / `thisMonth` / `lastMonth` / `custom` |
| `start_date` | string(date) | 否 | 自定义开始日期，`preset=custom` 时必填 |
| `end_date` | string(date) | 否 | 自定义结束日期，`preset=custom` 时必填 |

---

## 4. Response 顶层结构

成功响应遵循当前前端 `vben` 默认使用的标准 envelope：

- `code`
- `data`
- `message`

其中：

- `code=0` 表示成功
- `data` 承载真正的 Dashboard summary 业务数据
- `message` 为响应消息，当前成功默认返回 `ok`

---

## 5. data 字段

`data` 内部返回两个顶层字段：

- `dateRange`
- `summary`

---

## 6. dateRange 字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `preset` | string | 当前查询预设 |
| `startDate` | string(date) | 当前区间开始日期 |
| `endDate` | string(date) | 当前区间结束日期 |
| `compareStartDate` | string(date) | 对比区间开始日期 |
| `compareEndDate` | string(date) | 对比区间结束日期 |

---

## 7. summary 字段结构

每张卡片统一返回以下结构：

| 字段 | 类型 | 说明 |
|---|---|---|
| `value` | number | 主值 |
| `unit` | string | 单位 |
| `compareType` | string | `rate` 或 `value` |
| `compareValue` | number / null | 对比值 |
| `compareDirection` | string | `up` / `down` / `flat` |
| `subText` | string | 卡片副文案 |

---

## 8. compareType 说明

### `rate`

表示百分比变化，用于：

- `salesAmount`
- `orderCount`
- `avgOrderValue`
- `salesQuantity`

### `value`

表示绝对值变化，用于：

- `attachRate`
- `lowStockSkuCount`
- `sizeBreakStyleCount`
- `outOfSeasonStockQty`

---

## 9. compareDirection 说明

- `up`：上升 / 增加
- `down`：下降 / 减少
- `flat`：无变化

---

## 10. 字段清单

### 10.1 `summary.salesAmount`

销售额卡片数据

### 10.2 `summary.orderCount`

订单数卡片数据

### 10.3 `summary.avgOrderValue`

客单价卡片数据

### 10.4 `summary.salesQuantity`

销售件数卡片数据

### 10.5 `summary.attachRate`

连带率卡片数据

### 10.6 `summary.lowStockSkuCount`

低库存 SKU 数卡片数据

### 10.7 `summary.sizeBreakStyleCount`

缺码款数卡片数据

### 10.8 `summary.outOfSeasonStockQty`

过季库存件数卡片数据

---

## 11. 示例响应

```json
{
  "code": 0,
  "data": {
    "dateRange": {
      "preset": "last7days",
      "startDate": "2026-03-15",
      "endDate": "2026-03-21",
      "compareStartDate": "2026-03-08",
      "compareEndDate": "2026-03-14"
    },
    "summary": {
      "salesAmount": {
        "value": 12860,
        "unit": "CNY",
        "compareType": "rate",
        "compareValue": 12.6,
        "compareDirection": "up",
        "subText": "共 38 单"
      },
      "orderCount": {
        "value": 38,
        "unit": "单",
        "compareType": "rate",
        "compareValue": 8.1,
        "compareDirection": "up",
        "subText": "支付订单"
      },
      "avgOrderValue": {
        "value": 338,
        "unit": "CNY",
        "compareType": "rate",
        "compareValue": 5.4,
        "compareDirection": "up",
        "subText": "平均每单成交金额"
      },
      "salesQuantity": {
        "value": 86,
        "unit": "件",
        "compareType": "rate",
        "compareValue": 10.2,
        "compareDirection": "up",
        "subText": "平均每单 2.3 件"
      },
      "attachRate": {
        "value": 2.3,
        "unit": "件/单",
        "compareType": "value",
        "compareValue": 0.2,
        "compareDirection": "up",
        "subText": "件/单"
      },
      "lowStockSkuCount": {
        "value": 12,
        "unit": "个",
        "compareType": "value",
        "compareValue": 3,
        "compareDirection": "up",
        "subText": "近 7 天新增预警"
      },
      "sizeBreakStyleCount": {
        "value": 8,
        "unit": "款",
        "compareType": "value",
        "compareValue": 2,
        "compareDirection": "up",
        "subText": "近 7 天新增缺码"
      },
      "outOfSeasonStockQty": {
        "value": 126,
        "unit": "件",
        "compareType": "value",
        "compareValue": 18,
        "compareDirection": "down",
        "subText": "较上期减少"
      }
    }
  },
  "message": "ok"
}
```
