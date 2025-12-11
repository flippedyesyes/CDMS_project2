整体报告结构：
1. 实验总概括 
1.1 实现目标和成果
1.2 分工
2. 系统整体设计
2.1. 目录结构与项目模块

顶层逻辑：be/（后端业务）、fe/（测试 & 工具）、doc/（文档）、script/（数据脚本）、test_pictures/（以图搜书样本）等。
重点描述新增文件：
doc/relational_schema.md、doc/index_design.md、doc/db_best_practices.md
fe/test/test_buyer_model_errors.py、fe/test/test_search_model_additional.py、fe/test/test_dao_branches.py 等新增 pytest
test_pictures/*、script/generate_ocr_cache.py 等 OCR/以图搜书支持脚本
简述原有文件的职责（be/model, be/view, fe/access, script/test.sh 等）。
2.2  数据库设计

2.2.1关系型数据库部分（主载体）
ER 图展示：附图、文字说明实体与关系（User、Store、Book、Inventory、Order、OrderItem、BookSearchIndex）。
ER → 关系模式：列出七张核心表及扩展表，表格形式列字段、主键、外键。
规范化说明：除 book_search_index 外均满足 3NF（原子字段、复合主键完全依赖、无传递依赖），book_search_index 为全文检索特意保留冗余。
事务处理：解释 session_scope()、主要业务流程（下单/付款/取消/发货）如何在事务内完成并使用 with_for_update/回滚确保一致性。
索引策略：摘自 doc/index_design.md，逐表说明主键/复合索引/全文索引，重点说明 search 的 FULLTEXT + (store_id) + (updated_at, book_id) 设计。

2.2.2文档型数据库部分（Blob/长文本存储）
说明 blob 数据分离策略：图片与超阈值文本存入 MongoDB（集合 book），记录字段、存储格式（Base64 图片、长文本）。
描述与关系库的关联方式（通过 book_id 关联），以及在以图搜书场景中如何使用 Mongo 中的图片数据 + OCR 缓存。

具体看下面这段
### 正确地使用数据库和设计分析工具，ER图，从ER图导出关系模式，规范化，事务处理，索引

1. ER图，从ER图导出关系模式
先说明我们用 ER 图捕捉实体（User/Store/Book/Inventory/Order/OrderItem/BookSearchIndex 等）及多对多、一对多关系，并附上 doc/ER图.png。
描述如何从 ER 图导出 7 张核心表：users、stores、books、inventories、orders、order_items、book_search_index，
对应的字段、主键/外键在` doc/relational_schema.md `里已经列出，可以在报告里引用表格或截图。以及`表结构.docx`

2. 规范化
主业务表（users、stores、books、inventories、orders、order_items）我们按 3NF 设计：
字段全部原子；
inventories(store_id, book_id)、order_items(order_id, book_id) 的非主属性完全依赖组合主键；
用户余额、店铺名称等都保留在各自实体表，避免跨表冗余。
唯一刻意“反规范化”的是 book_search_index：为了支撑全文检索，把标题、标签、目录、简介等长文本复制了一份，这样 MySQL 的 FULLTEXT/LIKE 查询才能命中。可以在报告里说明「除搜索索引表外，其他表满足 3NF；book_search_index 出于性能考虑有冗余，是有意的优化」。
设计遵循 3NF：每张表只有与主键直接相关的字段，复合主键表的非主属性完全依赖整个主键，避免了传递依赖；**Blob/文本拆到 Mongo/文件系统**
亮点：混合存储设计：核心结构在 MySQL，blob/长文本在 Mongo，满足题目要求并且在以图搜书、搜索缓存等场景真正用上。
3NF：像 orders 中的 user_balance、store_name 等冗余属性没有出现，用户、店铺、订单、书籍都拆成独立表，避免“非主属性依赖非主属性”的情况；书籍的文本信息集中在 books / book_search_index，库存只保存数量/价格。
3. 事务处理
Session/事务封装：说明我们在 be/model/sql_conn.py 中提供 session_scope()（SQLAlchemy Session + contextmanager），所有模型（Buyer, Seller, User, Search 等）都在这个作用域里执行数据库操作，自动 commit/rollback，确保同一业务流程（如下单、付款、发货）是一个原子事务。
关键流程的并发一致性：
Buyer.new_order()：同一事务里校验库存 → 扣减库存 → 创建订单和明细。任何步骤异常（库存不足、JSON 解析失败）都会触发 except 分支、日志记录并 rollback。
Buyer.payment()：先取消过期订单，再在一个事务里校验用户/店铺/卖家 → 扣减买家余额 → 增加卖家余额 → 更新订单状态。如果任何 DAO 返回 False（余额不足、卖家不存在、状态冲突），立即返回错误码，不会发生部分更新。
Buyer.cancel_order()：拿到订单后恢复库存、更新订单状态也在一个事务里；测试里模拟 update_order_status 抛异常，验证库存先恢复再 rollback，体现事务控制。
Seller.ship_order() / buyer.confirm_receipt()：一样用 session_scope()，保证状态变更、时间戳写入是互斥的。
Search.search_books_by_image() 在 fallback 时只是读取，不需事务；但 recommend_by_tags 使用查询 + 聚合，仍在 session 范围内，读取一致快照。
异常处理：模型层捕获 BaseException，日志记录后返回 530，这时 session_scope 的 except 路径会先 rollback 再抛出，防止半提交状态。
并发安全：虽然没有显式锁语句，SQLAlchemy 默认的事务隔离（InnoDB）配合 with_for_update()（在 order_dao.adjust_inventory_for_items 中读取库存行时使用）保证了扣库存的串行化，避免“超卖”。
*总结时就写*：我们通过 SQLAlchemy session 封装+with_for_update 实现 ACID；关键流程（下单/付款/取消/发货）都在事务内完成，出现异常会 rollback；DAO 层 error 返回后模型层不会继续提交。这样就把“事务处理”说明清楚了。
4. 索引
详见 `doc/index_design.md`）：用户表 user_id PK + status; 订单表 (buyer_id, status)、(status, updated_at)；库存表 (store_id, book_id)；order_items、book_search_index 各有合适的组合索引。搜索场景中 book_search_index 采用 MySQL FULLTEXT（title/author/tags/catalog/intro/content），并辅以 store_id 普通索引、(updated_at, book_id) 组合索引实现高效全文检索与分页

3. 功能展示
3.1 从文档型到关系型的迁移

迁移动机
Lab1 基于 MongoDB，库存和订单分散在多个集合，无真正事务，跨集合恢复库存/扣款时容易出现不一致；全文检索依赖脚本过滤，性能有限。
迁到 MySQL 后使用 SQLAlchemy session + InnoDB 事务，保证库存扣减、下单/付款等流程具备 ACID；SQL 查询、索引和 ORM 让筛选、统计和代码维护成本大幅下降。

数据表设计的改动
原 Mongo 集合	新 MySQL 表及说明
user	users：user_id PK、password、balance、status、token，status 有普通索引用于过滤。
store	stores + inventories：store 基本信息和 book 库存拆表；inventories 以 (store_id, book_id) 为复合主键，并对 updated_at 建索引。
order	orders + order_items：订单头记录状态/金额/时间戳，order_items 用 (order_id, book_id) 存明细，支持事务恢复库存。
book（轻量文本）	books：书籍静态属性（title、author、价格等）。
book（长文本/图片）	继续存 Mongo：图片 Base64、长文本描述 > 阈值的部分仍在 book 集合，通过 book_id 关联。
——	book_search_index（新增）：关系库中的全文索引表，冗余存 title/tags/catalog/intro 并建 FULLTEXT + (store_id) 等索引，加速搜索。

具体迁移代码的关键实现
数据导入：script/import_books_to_sql.py 负责把 book.db/ book_lx.db 迁移到 MySQL，同时将图片/长文本分流到 Mongo (script/export_sample_covers.py)。
业务改写：be/model/buyer.py, seller.py, search.py 等模块全部改用 SQLAlchemy session；强调我们不复用旧 Mongo 逻辑。
新特性：借助关系库做了事务包装（订单流程、库存恢复）、新增的接口（批量上架、订单导出、以图搜书、标签推荐）怎样依托新的 schema 与索引。
（概括：“be/model/buyer.py、seller.py、user.py 等业务模块全部改成使用 sql_conn.session_scope() 和 DAO；be/model/search.py 新增了全文检索、以图搜书逻辑；fe/access/fe/test 中配套加了新接口测试”。）

接下来是功能具体撰写
一个例子
3.x 用户注册 POST /auth/register
接口

请求体：{"user_id": "...", "password": "...", "terminal": "browser/android/..."}
返回：code, message；成功时附带 JWT token（CheckToken 流程复用）。
后端逻辑（be/view/auth.py → be/model/user.py）

通过 User.register() 进入 session_scope()，生成初始 token + terminal。
先到 user_dao.get_user(include_inactive=True) 检查是否已存在；若已删除状态则调用 user_dao.revive_user，否则拒绝重复注册。
新用户调用 user_dao.create_user() 写入 SQL，默认 balance=0、status=active。
任何 DAO 抛异常都会被捕获并 rollback，返回 error_exist_user_id 或 530。
数据库操作（MySQL）

users 表结构：user_id PK、password、balance、token、terminal、status、created_at。
注册流程涉及一次 SELECT（检查是否存在），一次 INSERT/UPDATE（新增或回收软删除用户）。user_id 为主键，status 有普通索引用于筛选。
相比 Lab1（Mongo 集合中直接插入 JSON），现在所有改动都通过 ORM + schema 限制，token/状态/余额字段都强类型化。
测试用例（fe/test/test_user_model_extra.py）

测试场景	传参	结果 message / code
新用户注册	(user_id=new_uuid, password)	code=200, message="ok"
重复注册失败	(user_id=existing, password)	error_exist_user_id
软删除后重新注册恢复	先注销再注册	code=200, 确认 revive 路径被触发
DAO 写入失败（mock update_token）	monkeypatch user_dao.update_token 返回 False	error_authorization_fail，验证事务回滚
这样既说明接口行为，又突出“使用关系型 DAO + 事务 + 测试验证”的改动。其它功能（登录、下单、批量上架、以图搜书等）可以沿用同样模版撰写。

顺序：
3.2 60% 基础功能（原项目自带的接口全部迁移到 MySQL）
用户注册 / 注销 / 登录 / 改密（/auth/register, /auth/login, /auth/logout, /auth/password）
店铺创建（/seller/create_store）
卖家上架与补货（/seller/add_book, /seller/add_stock_level）
买家充值（/buyer/add_funds）
买家下单、付款与取消（/buyer/new_order, /buyer/payment, /buyer/cancel_order）
买家查询订单（/buyer/orders）
→ 这些都重写成 SQLAlchemy + MySQL 版本，测试文件 fe/test/test_*.py 中的 60% 用例全部通过。

3.3 40% 拓展功能（原项目第二阶段要求）
发货 / 收货流程（/seller/ship_order, /buyer/confirm_receipt）
自动取消超时订单、订单列表分页与状态过滤（/buyer/orders 扩展参数）
搜索图书：关键字搜索（/search/books）与分页、店铺范围
订单状态、订单查询、取消订单的边界处理
→ 这些接口与测试也全部迁移到关系库，相关用例如 test_shipping_flow.py, test_order_management.py, test_search_books.py。

3.4 新增接口（本次新增的 4 个功能，2 个偏简单，2 个偏复杂）（这几个功能讲一下测试的逻辑，后面两个详细讲！！）
简单接口：
批量上架 POST /seller/batch_add_books（支持一次导入多本书并返回逐条结果）。
订单导出 GET /buyer/export_orders（支持 JSON/CSV，供报告/财务使用）。
复杂接口：
以图搜书 POST /search/books/image（上传书封面或指定缓存图片，走 OCR→全文索引→Mongo fallback）。
亮点：以图搜书 + OCR 缓存：把书封面导出为图片、通过大模型 OCR 生成文字，再落地缓存 test_pictures/ocr_results.json，实现 POST /search/books/image；这是一个比原项目更复杂的检索功能，既展示混合存储能力，又体现 AI + 数据库结合。
标签推荐 GET /search/recommend_by_tags（多标签聚合销量、按 store 过滤，提供推荐列表）。
亮点：book_search_index 的 FULLTEXT + recommend_by_tags 的销量聚合 + 标签过滤，是一次完整的性能优化案例，配套 doc/index_design.md 和 explain 分析。

4. 结果展示

4.1 测试结果
所有 pytest 用例均可通过 .\.venv\Scripts\python -m pytest -v --ignore=fe/data（见 script/test.sh，实际执行使用 coverage run ... pytest ...），包含 60% 基础 + 40% 拓展 + 新增接口 + DAO/bench/unit 测试，运行日志已截留（frontend begin test → frontend end test）。

4.2覆盖率
coverage run --timid --branch --source fe,be --concurrency=thread -m pytest -v --ignore=fe/data 后，coverage report 显示 statement 95%、branch 82%、总体 94%。为提升覆盖率，我们补了：

fe/test/test_buyer_model_errors.py：新增 cancel_expired_orders、支付余额不足/回滚、确认收货状态校验等分支测试；
fe/test/test_search_model_additional.py：覆盖默认分页、OCR override、缓存命中、DAO 异常、limit clamp 等路径；
fe/test/test_seller_model_errors.py：补 add_book/create_store/add_stock_level 成功分支与 ship_order 权限检查；
fe/test/test_dao_branches.py：直接测试 order_dao/user_dao 的 rowcount/余额分支；
fe/test/test_user_model_extra.py：新增 logout 成功、UUID 注册、check_token 成功等 case；
fe/test/test_bench_workload.py：覆盖 workload 的 get_new_order/update_stat 逻辑。

4.3 索引性能分析
 doc/index_design.md

5. 版本控制
