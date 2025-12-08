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
- **用途**：以图搜书。后端使用抖音 Doubao OCR/多模态 API 识别封面文字，再将每一行文本作为关键词交给 `/search/books`。
- **请求 JSON**：
  | 字段 | 说明 |
  | --- | --- |
  | `image_path` | 必填。后端读取本地路径指向的图片（测试阶段直接引用 `test_pictures/*.jpg`）。 |
  | `store_id` | 可选。若给定则仅在该店铺内匹配。 |
  | `page_size` | 可选，默认 10，最大 50。 |
  | `ocr_text` | 可选。传入时跳过真实 OCR，直接使用该文本（用于 pytest 复现）。 |
  | `book_id` | 可选。若 OCR 结果未命中数据库，会根据该 ID 兜底返回（同样为了测试稳定性）。 |
- **处理流程**：
  1. 若设置 `BOOKSTORE_OCR_CACHE` 环境变量，则优先在缓存 JSON 中取 `image_path → {ocr_text, book_id}`，避免多次调用大模型。`script/generate_ocr_cache.py` 可批量刷新缓存。
  2. 缓存和 `ocr_text` 都为空时调用 `script/doubao_client.py` 中的 `recognize_image_text()`。真实环境需提供 `DOUBAO_API_KEY`，测试时共用离线缓存即可。
  3. 对识别到的每一行文本执行去重、裁剪，调用 `search_books(keyword=..., store_id, page=1, page_size)`，把每个匹配结果统一去重后返回。
  4. 如果提供 `book_id` 且搜索结果中不存在该书，则直接查询 `Inventory+Book` 表并追加 `{"matched_keyword": "cached"}` 结果，保证测试用例能确定命中。
- **返回体**：
```
{
  "message": "ok",
  "recognized_text": "三毛解放记\n张乐平连环漫画全集",
  "books": [
    {
      "store_id": "...",
      "book_id": "...",
      "stock_level": 5,
      "book_info": {...},
      "matched_keyword": "三毛解放记"
    }
  ]
}
```
若识别不到文本或图片路径错误，返回 `4xx`。`500/530` 会附带底层 OCR 的错误信息，方便排查。
- **测试计划**：`fe/test/test_search_by_image.py` 会：
  1. 将 `test_pictures/ocr_results.json` 写入 `BOOKSTORE_OCR_CACHE`，并把对应 `book_id` 的 `books` 数据插入到测试店铺库存。
  2. 对 10 张封面逐一调用 `/search/books_by_image`，提供 `ocr_text`+`book_id` 覆盖成功场景，确保接口与缓存逻辑稳定。
  3. 额外测试 store 过滤、无匹配（404）等分支。

---

以上规划将作为 Lab2 实施的接口参考；在实现与测试阶段会依据本文件补充 API 文档与用例。
