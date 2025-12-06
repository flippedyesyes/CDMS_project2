# Bookstore 关系型数据库设计

基于当前 ER 图抽取出的核心表共 6 张，并额外设计了一张书籍搜索索引表，便于全文搜索和分页查询。每张表的字段、主外键及约束如下。

## 1. `user`
| 字段 | 类型 | 说明 | 约束 |
| --- | --- | --- | --- |
| `user_id` | VARCHAR | 用户唯一 ID | **PK** |
| `password_hash` | VARCHAR | 密码哈希 | NOT NULL |
| `balance` | BIGINT | 账户余额，单位为分 | 默认 0，CHECK >=0 |
| `status` | VARCHAR | 账户状态（active / disabled ...） | NOT NULL |
| `created_at` | TIMESTAMP | 注册时间 | NOT NULL |

## 2. `bookstore`
| 字段 | 类型 | 说明 | 约束 |
| --- | --- | --- | --- |
| `store_id` | VARCHAR | 店铺唯一 ID | **PK** |
| `owner_user_id` | VARCHAR | 店主用户 ID | FK → `user(user_id)` |
| `name` | VARCHAR | 店铺名称 | NOT NULL |
| `description` | TEXT | 店铺描述 | 可空 |
| `status` | VARCHAR | 店铺状态 | NOT NULL |
| `created_at` | TIMESTAMP | 创建时间 | NOT NULL |

## 3. `book`
| 字段 | 类型 | 说明 | 约束 |
| --- | --- | --- | --- |
| `book_id` | VARCHAR | 图书唯一 ID（沿用原数据） | **PK** |
| `title` | VARCHAR | 书名 | NOT NULL |
| `author` | VARCHAR | 作者（多作者以分隔符存储） | NOT NULL |
| `publisher` | VARCHAR | 出版社 | 可空 |
| `pub_year` | VARCHAR | 出版年份 | 可空 |
| `pages` | INT | 页数 | 可空 |
| `price` | BIGINT | 建议零售价（分） | 可空 |
| `currency_unit` | VARCHAR | 价格货币单位 | 默认 CNY |
| `intro_excerpt` | TEXT | 图书简介摘录（用于展示/搜索） | 可空 |
| `cover_ref` | VARCHAR | 封面外部存储引用 | 可空 |
| `has_external_longtext` | BOOLEAN | 是否存在外部长文本 | 默认 FALSE |

## 4. `order`
| 字段 | 类型 | 说明 | 约束 |
| --- | --- | --- | --- |
| `order_id` | VARCHAR | 订单编号 | **PK** |
| `user_id` | VARCHAR | 买家 ID | FK → `user(user_id)` |
| `store_id` | VARCHAR | 店铺 ID | FK → `bookstore(store_id)` |
| `status` | VARCHAR | 订单状态（pending/paid/shipped/...） | NOT NULL |
| `total_price` | BIGINT | 订单总价（分） | NOT NULL |
| `created_at` | TIMESTAMP | 创建时间 | NOT NULL |
| `payment_time` | TIMESTAMP | 付款时间 | 可空 |
| `shipment_time` | TIMESTAMP | 发货时间 | 可空 |
| `delivery_time` | TIMESTAMP | 收货时间 | 可空 |
| `expires_at` | TIMESTAMP | 待支付超时时间 | 可空 |

## 5. `inventory`
书店与图书的连接表。

| 字段 | 类型 | 说明 | 约束 |
| --- | --- | --- | --- |
| `store_id` | VARCHAR | 店铺 ID | **PK1**, FK → `bookstore(store_id)` |
| `book_id` | VARCHAR | 图书 ID | **PK2**, FK → `book(book_id)` |
| `stock_level` | INT | 当前库存 | CHECK >=0 |
| `price` | BIGINT | 店内售价（分） | NOT NULL |
| `search_text` | TEXT | 搜索文本（标题/标签拼接） | 可空 |
| `updated_at` | TIMESTAMP | 最近更新时间 | NOT NULL |

> 复合主键 `(store_id, book_id)` 保证同一店铺内同一本书唯一。可在 `store_id`、`book_id` 上额外建立索引以支撑分页。

## 6. `order_item`
订单与图书的连接表。

| 字段 | 类型 | 说明 | 约束 |
| --- | --- | --- | --- |
| `order_id` | VARCHAR | 订单 ID | **PK1**, FK → `order(order_id)` |
| `book_id` | VARCHAR | 图书 ID | **PK2**, FK → `book(book_id)` |
| `count` | INT | 购买数量 | CHECK >=1 |
| `unit_price` | BIGINT | 成交单价（分） | NOT NULL |

## 7. `book_search_index`
为了加速关键词搜索，单独维护书籍索引表，与 `book` 一一对应。

| 字段 | 类型 | 说明 | 约束 |
| --- | --- | --- | --- |
| `book_id` | VARCHAR | 图书 ID | **PK**, FK → `book(book_id)` |
| `title` | VARCHAR | 标准化后的标题 | NOT NULL |
| `subtitle` | VARCHAR | 副标题 | 可空 |
| `author` | VARCHAR | 作者（标准化） | NOT NULL |
| `tags` | TEXT | 标签集合（序列化） | 可空 |
| `catalog_excerpt` | TEXT | 目录摘录 | 可空 |
| `intro_excerpt` | TEXT | 简介摘录 | 可空 |
| `content_excerpt` | TEXT | 正文摘录 | 可空 |
| `search_vector` | TSVECTOR / TEXT | 供全文检索使用的向量或拼接文本 | 可空 |
| `updated_at` | TIMESTAMP | 最近同步时间 | NOT NULL |

> 搜索接口只需访问本表即可完成关键词匹配，必要时将 `search_vector` 建 GIN/FULLTEXT 索引。原始长文本、图片等大字段保存在对象存储或 NoSQL 中，通过 `book.cover_ref`、`has_external_longtext` 等字段指向。

---

上述结构覆盖了主干业务：注册/开店、上架维护库存、下单支付发货、关键词搜索等。后续若需扩展（如用户 token、订单日志、支付记录等），可在此基础上新增附属表，但不会影响现有关系模式。
