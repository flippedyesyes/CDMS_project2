# 数据库规范化与事务策略

本节补充“正确地使用数据库和设计分析工具”条目下尚未覆盖的规范化与事务处理内容，可直接引用到报告。

## 1. 规范化分析

为兼顾测试可读性与性能，关系模式遵循 3NF 设计原则：

1. **主键依赖**：所有非主属性均完全依赖主键。例如 `orders` 中的 `total_price`、`status` 仅依赖 `order_id`；`inventories` 中的 `stock_level`、`updated_at` 仅依赖复合主键 `(store_id, book_id)`。
2. **消除传递依赖**：用户余额、密码哈希等不与店铺/订单同表存储，避免跨实体的传递依赖。`book_search_index` 将全文字段从 `books` 分离，既消除了 `books` → `store` → `search range` 的传递依赖，又缩短一行的宽度，便于索引。
3. **最小冗余**：
   - `book_search_index` 只复制必要的文本摘要，与 `books` 通过 `book_id` 对齐，保持冗余可控。一旦 `books` 更新，DAO 同时更新索引表以维持一致。
   - 大字段（封面、长介绍、内容全文）存入 MongoDB `book_blob` 集合，MySQL 中只保留引用与 `has_external_longtext` 标记，避免 BLOB 扩散到 OLTP 表。
   - `order_items` 独立成表，既避免在 `orders` 中存数组型字段，又为后续加上促销/退款等字段提供拓展空间。

此设计既满足 3NF，又通过专用索引/分表保证查询效率。

## 2. 事务处理策略

`be/model/sql_conn.py` 提供 `session_scope()` 上下文管理器；所有跨表写操作（充值、下单、支付、取消、发货、收货）均在同一事务中完成，避免出现“库存扣减成功但订单未创建”的不一致场景。关键策略如下：

| 场景 | 事务边界 | 隔离/锁使用 | 说明 |
| --- | --- | --- | --- |
| 用户注册/登录/改密 | 单表事务，在 `users` 上执行 INSERT/UPDATE | 默认 InnoDB `REPEATABLE READ`；利用唯一键防止并发重复注册 | 失败自动回滚，API 返回 5xx 错误码。 |
| 卖家上架/补库存 | 更新 `books` / `inventories` | `inventories` 记录采用 `SELECT ... FOR UPDATE`，避免并发补货导致计数错误 | 同一个 `(store_id, book_id)` 的库存记录在事务内唯一。 |
| 买家下单 | 插入 `orders`、`order_items`，扣库存 | 依次 `SELECT inventory FOR UPDATE` → 判断库存 → 写订单；失败回滚库存 | 保证库存与订单一致。 |
| 付款 | 更新 `orders.status`、买家/卖家余额 | 在 `users` 表上锁定两方余额，确保资金只扣/加一次；禁止重复支付通过状态机控制 | 事务失败时订单状态保持 `pending`。 |
| 取消订单（主动/超时） | 更新 `orders.status`，恢复库存 | 先锁定订单，校验 `status`，再归还库存；若订单已付款，触发退款逻辑 | 自动任务利用 `idx_orders_status_updated` 快速挑出超时单。 |
| 发货/收货 | 更新订单 `status` + `shipment_time/delivery_time` | `SELECT ... FOR UPDATE` 确保状态单调：`paid -> shipped -> delivered` | 违反状态机直接返回错误码。 |

事务隔离级别采用 MySQL InnoDB 默认 `REPEATABLE READ`，结合显式 `SELECT ... FOR UPDATE` 控制热点记录。所有 DAO 函数通过自定义异常传递失败原因，业务层可统一转换为 HTTP 状态码。

## 3. 与 Mongo 方案的对比

- Lab1 中的 MongoDB 操作为“无事务 + 应用层补偿”；在高并发场景中只能依赖 `$inc` 和写冲突重试，无法保证跨集合一致性。Lab2 改用 MySQL 事务后，库存、订单、余额的多表更新一次提交即可，逻辑更清晰。
- 规范化设计让关系模式清晰、利于索引；Mongo 的嵌套结构在查询时需要拆 JSON，索引粒度有限，性能受影响。

综上，通过规范化的关系模式 + 事务化的 DAO 层，满足了课程对于“正确地使用数据库、从 ER 导出关系、规范化、事务处理、索引”的要求。
