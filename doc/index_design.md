# 索引与数据存储设计说明

本文档汇总当前关系型数据库与 MongoDB 的结构、各类索引及其用途，便于在报告和后续开发中引用。除特别说明外，所有表均位于 MySQL `bookstore` 数据库中。

## 1. 表与索引

| 表 | 关键字段/索引 | 设计意图 |
| --- | --- | --- |
| `users` | `PRIMARY KEY (user_id)`<br>`INDEX idx_users_status(status)` | 主键用于登录/权限验证；状态索引用于排除注销账号、统计活跃用户。 |
| `stores` | `PRIMARY KEY (store_id)`<br>`INDEX idx_stores_owner(owner_id)` | 店铺查询通常需要按创建者过滤；索引保证 `seller.list_stores`/店铺注销性能。 |
| `books` | `PRIMARY KEY (book_id)`<br>`UNIQUE KEY uq_books_title_isbn(title, isbn)`<br>`INDEX idx_books_updated(updated_at)` | 保证图书唯一性，避免重复导入；`updated_at` 支撑增量同步与分页。 |
| `inventories` | `PRIMARY KEY (store_id, book_id)`<br>`INDEX idx_inventories_updated(updated_at)` | 复合主键即库存唯一性（一个店铺一本书只有一条记录）；更新索引用于库存盘点和“低库存提醒”。 |
| `orders` | `PRIMARY KEY (order_id)`<br>`INDEX idx_orders_buyer_status(buyer_id, status)`<br>`INDEX idx_orders_status_updated(status, updated_at)` | 买家端按状态分页查单与后台的自动超时任务均依赖这些索引；写入遵循先 `order` 后 `order_items` 的事务。 |
| `order_items` | `PRIMARY KEY (order_item_id)`<br>`UNIQUE KEY uq_order_items_order_book(order_id, book_id)`<br>`INDEX idx_order_items_order(order_id)` | `order_id` 索引让加载订单明细 O(log n)；联合唯一约束防止同一本书重复出现在同一订单。 |
| `book_search_index` | `PRIMARY KEY (book_id)`<br>`FULLTEXT INDEX ft_book_search(title, author, tags, catalog, intro_excerpt, content_excerpt)`<br>`INDEX idx_book_search_store(store_id)`<br>`INDEX idx_book_search_updated(updated_at, book_id)` | 搜索表拆分自 `books`，仅保留正文摘要。FULLTEXT 负责标题/作者/标签/目录/摘要/内容检索；`store_id` 索引用于店铺范围过滤；`(updated_at, book_id)` 组合索引用于增量刷新与稳定分页。 |
| `user_tokens`（如启用） | `PRIMARY KEY (token)`<br>`INDEX idx_tokens_user(user_id)` | 支持多终端登录；失效处理按 `expires_at` 列排序。 |

## 2. MongoDB 存储

- 数据库：`bookstore`（Mongo 实例）  
- 集合：
  - `book_blob`：存放图书封面 `picture`（BLOB）以及超长文本（超过 4 KB 的 `author_intro`/`book_intro`/`content`）。
  - 文档结构示例：
    ```json
    {
      "book_id": "1361264",
      "doc_type": "book_blob",
      "picture": <Binary>,
      "long_intro": "...",
      "long_content": "..."
    }
    ```
- MySQL `books.has_external_longtext=1` 表示该记录需要到 Mongo 中拼接详细信息。API 层优先命中 MySQL，若字段为空且标记为 `has_external_longtext`，再访问 Mongo。

## 3. 搜索优化设计

### 3.1 设计动机

Lab1 使用 MongoDB `text index`，无法同时满足：
1. 店铺内搜索（缺乏与 `store_id` 的复合索引）。
2. 分页排序（Mongo text score 不能与 `updated_at` 协同）。
3. 大规模数据导入后性能急剧下降。

Lab2 的处理方式：
- 将可全文检索的字段复制到 `book_search_index`，采用 InnoDB + FULLTEXT。
- 通过 `MATCH ... AGAINST (? IN BOOLEAN MODE)` 搜索标题、作者、标签、目录、摘要、内容。
- 如果输入关键词长度不足或数据库 FULLTEXT 未开启，自动回退到 `LIKE` 查询，避免 0 结果。

### 3.2 查询流程与实现细节

1. 前端传递 `keyword`、`store_id`（可选）、`page`、`page_size`、`scope`（字段范围）等参数。
2. `be/model/dao/search_dao.py` 会优先构造 `MATCH(...) AGAINST (? IN BOOLEAN MODE)` 语句。如果数据库禁用了 FULLTEXT 或关键字不足 3 个字符，自动退化为 `LIKE '%kw%'`，保证测试与回归时不会出现空结果。
   ```sql
   SELECT book_id, title, author, pub_year, price
     FROM book_search_index
    WHERE MATCH(title, author, tags, catalog, intro_excerpt, content_excerpt) AGAINST (:kw IN BOOLEAN MODE)
      AND (:store_id IS NULL OR store_id = :store_id)
    ORDER BY MATCH(...) AGAINST (:kw IN BOOLEAN MODE) DESC, updated_at DESC
    LIMIT :offset, :page_size;
   ```
3. 若 scope 限制为标题/作者等，则只对相应字段构建 MATCH 表达式，减少噪音；`store_id` 条件命中 `idx_book_search_store` 索引。
4. 分页参数直接映射为 `LIMIT/OFFSET`，所有排序在 SQL 层完成；之后根据返回的 `book_id` 回到 `books` 表补齐价格/库存信息。

### 3.3 亮点

- **全文索引 + 范围过滤**：借助单独的 `book_search_index`，全文索引不会被高频写入的库存数据拖慢；`store_id` 索引可实现“全站/店铺内”搜索切换。
- **分页与排序**：`updated_at` 索引在结果集排序时避免了回表扫描，配合 `book_id` 作为 tie-breaker 可稳定分页。
- **阈值拆分长文本**：将超过 4 KB 的介绍/目录移动到 Mongo，只在 MySQL 保留摘要，减少 FULLTEXT 记录大小，提高倒排索引密度。

## 4. 事务与一致性概述

- 下单/付款/取消等流程在 DAO 层通过 `session_scope()` 包裹事务，确保库存、余额、订单状态同步更新。
- `orders.status` 列仅允许在事务内单向更新（`pending -> paid -> shipped -> delivered` 或 `pending -> cancelled`），借助 `FOR UPDATE` 防止并发写入。
- 自动取消超时订单的逻辑利用 `idx_orders_status_updated` 快速扫描 `status='pending' AND updated_at < now() - timeout`。

## 5. 与文档数据库方案的对比

| 方面 | Lab1 (Mongo) | Lab2 (MySQL + Mongo) | 优势 |
| --- | --- | --- | --- |
| 主数据存储 | 单一 Mongo 集合 | 7 张关系表 + Mongo 存 BLOB | 支持事务、外键、复杂 JOIN |
| 搜索索引 | Mongo text index | MySQL FULLTEXT + store 过滤 + Mongo 备用 | 查询性能提升 + 更易分页 |
| 数据同步 | 应用层手动去重 | ORM + 唯一约束控制 | 防止重复导入、易维护 |
| 长文本/图片 | 与正文同表 | 拆分至 Mongo `book_blob` | 避免拖慢 OLTP，仍可按需加载 |

---

book_search_index：book_id 主键解释，同时：
FULLTEXT(title,author,tags,catalog,intro_excerpt,content_excerpt) 覆盖正文检索；
普通索引 store_id 用于店铺范围过滤；
组合索引 (updated_at, book_id) 供增量同步分页。
user_tokens / payments 若有：各自主键 + 需要的外键索引。
对应搜索优化：be/model/dao/search_dao.py 在查询时优先用 MATCH(...) AGAINST (? IN BOOLEAN MODE) 命中 FULLTEXT；若 MySQL 未开启全文或关键词过短，退化为 LIKE。分页参数 (page, page_size) 映射到 SQL LIMIT/OFFSET，store_id 条件走普通索引，全文结果再 intersect。对比之前 MongoDB 仅有文本索引 + 脚本过滤，现在关系库实现了：

搜索字段拆分到 book_search_index，保持行宽短、可独立维护；
FULLTEXT + store 索引组合，减少大范围扫描；
结果分页完全在 SQL 层完成，避免 Python 层切片。