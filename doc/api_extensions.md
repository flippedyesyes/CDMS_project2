# 40% 功能接口规划

围绕“发货→收货”“搜索”“订单状态/查询/取消”三块功能，以下为计划在 Lab2 中落实的接口细节与扩展点。所有接口仍复用现有 URL，仅新增可选参数或明确状态流。

## 1. 发货 → 收货流程

### `/seller/ship_order` (POST)
- **请求体**：`user_id`、`store_id`、`order_id`。
- **前置条件**：订单状态为 `paid`，且 `store_id` 与订单匹配。
- **状态流**：`pending` → `paid` → `shipped`。调用后写入 `shipment_time=now` 并设置 `status="shipped"`。
- **错误码**：保持原逻辑（门店不存在、状态非法等）。

### `/buyer/confirm_receipt` (POST)
- **请求体**：`user_id`、`order_id`。
- **前置条件**：订单状态为 `shipped`。
- **状态流**：`shipped` → `delivered`。调用后写入 `delivery_time=now` 并设置 `status="delivered"`。
- **响应**：`{ "message": "ok" }`。

### 订单状态字段
`status` 字段将覆盖以下枚举：`pending`, `paid`, `shipped`, `delivered`, `cancelled`, `cancelled_timeout`, `cancelled_by_seller`（预留）。文档及实现中需保持一致。

## 2. 搜索接口 `/search/books` (GET)

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `q` | string (optional) | 关键词，可输入多词。|
| `store_id` | string (optional) | 限定店铺搜索。|
| `scope` | string (optional) | 搜索范围：`title` / `tags` / `catalog` / `content` / `all`，默认 `all`。|
| `sort` | string (optional) | 排序字段：`score`, `updated_at`, `price` 等，默认匹配度。|
| `page` | int (≥1) | 页码，默认 1。|
| `page_size` | int (1~50) | 每页条数，默认 20。|

**返回体**：
```
{
  "message": "ok",
  "page": 1,
  "page_size": 20,
  "total": 123,
  "books": [
    {
      "store_id": "...",
      "book_id": "...",
      "stock_level": 10,
      "price": 6000,
      "book_info": {...},
      "score": 3.21
    }
  ]
}
```

**实现要点**：
- 使用 `book_search_index` 表或全文索引 (`tsvector`/FULLTEXT) 支撑 `q`、`scope` 的匹配。
- 在 `inventory` 上联合查询库存/价格，分页采用 `LIMIT/OFFSET`。

## 3. 订单状态 / 查询 / 取消

### `/buyer/orders` (GET)
新增可选查询参数：
- `status`：过滤特定状态。
- `created_from` / `created_to`：下单时间区间。
- `sort_by`：`updated_at`（默认）、`created_at`、`total_price`。
- `page`, `page_size`：分页（默认 1 / 20，最大 50）。

响应保留 `{ page, page_size, total, orders: [...] }` 结构，`orders` 中包含完整订单对象（含 `status`, `payment_time`, `shipment_time`, `delivery_time`, `expires_at` 等）。

### `/buyer/cancel_order` (POST)
- **请求体**：`user_id`、`order_id`、`password`（可选，用于前端需要重新验证时）。
- **前置条件**：订单状态为 `pending`。
- **处理**：恢复库存、记录 `cancelled_at`、状态置为 `cancelled`。

### 自动取消超时订单
- 触发点：在 `buyer.Buyer` 中提供 `cancel_expired_orders()`，在下单、付款、取消等入口调用；必要时可在后台任务/测试前置调用。
- 逻辑：若 `status="pending"` 且 `expires_at <= now`（或创建时间超过阈值），转 `cancelled_timeout` 并恢复库存。

### 取消/状态查询扩展
- `GET /buyer/orders` 和 `POST /buyer/cancel_order` 的错误码、返回结构与 Lab1 保持一致，仅记录在报告中以说明新增的过滤参数与状态枚举。

---

# 额外拓展接口（加分项）

## `/seller/batch_add_books` (POST)
- **用途**：卖家一次性上架多本书，加速导入大数据集。
- **请求体**：
```
{
  "user_id": "...",
  "store_id": "...",
  "books": [
    {
      "book_info": {...},   // 同 add_book
      "stock_level": 100
    },
    ...
  ]
}
```
- **行为**：在单个事务中依次执行 `add_book` 逻辑（若存在则跳过或返回错误），写入 `inventory` 并记录结果。
- **响应**：
```
{
  "message": "ok",
  "results": [
    {"book_id": "xxx", "code": 200, "message": "ok"},
    {"book_id": "yyy", "code": 516, "message": "exist book id"}
  ]
}
```
- **测试计划**：新增 pytest（例如 `fe/test/test_seller_batch_add.py`），覆盖成功上架、多本中部分失败、事务一致性等场景。

## `/buyer/orders/export` (GET)
- **用途**：买家导出订单历史（CSV/JSON），便于成绩展示或报表。
- **请求参数**：`user_id`, `status?`, `created_from?`, `created_to?`, `format`(`csv`/`json`, 默认 `json`)。
- **行为**：重用 `/buyer/orders` 的过滤和分页逻辑，若 `format=csv` 则返回文本/文件流；`json` 返回 `{orders: [...]}`。
- **响应（JSON 示例）**：
```
{
  "message": "ok",
  "orders": [
    {"order_id": "...", "status": "...", "total_price": 12345, ...}
  ]
}
```
- **测试计划**：在 `fe/test/test_buyer_export.py`（或现有订单测试中新增用例）验证 JSON 导出、CSV 导出及过滤条件。

## `/search/books_by_image` (POST)
- **用途**：以图搜书。用户上传封面照片，后台执行 OCR/大模型识别后按文字搜索书籍。
- **请求体**：
```
{
  "image_base64": "...",   // 或 multipart 文件
  "store_id": "optional",
  "page": 1,
  "page_size": 10
}
```
- **处理流程**：
  1. 将 `image_base64` 解码为 bytes（或直接读取上传文件）。
  2. 使用 OCR/大模型 API 识别封面文字，提取书名/作者关键词。
  3. 调用现有搜索逻辑（`q=识别文本`, `scope=title,author,content` 等）并分页返回结果。
- **返回体**：与 `/search/books` 保持一致 `{message, page, page_size, total, books:[...]}`；若识别失败返回 `400` 与错误信息。
- **测试计划**：新增 `fe/test/test_search_by_image.py`，准备若干封面图片（从 `book_lx.db` 导出），模拟/Mock OCR 输出并断言接口返回包含对应 `book_id`；覆盖文件缺失、无匹配、store 过滤等场景。

---

以上规划将作为 Lab2 实施的接口参考；在实现与测试阶段会依据本文件补充 API 文档与用例。
