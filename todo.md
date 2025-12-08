综合工作大纲

阶段 0：基线评估与拆分

盘点可直接复用的层（Flask 蓝图、fe/test 测试、业务类对外接口）以及必须重构的部分（be/model/mongo.py、db_conn.py、所有直接操作 Mongo 的逻辑）。
列出 User/Seller/Buyer/Search 四大模型中所有访问数据层的函数，标注读写类型、是否要事务，形成 DAO 设计输入。
阶段 1：接口与扩展规划（满足要求1）

保持 60% 基础接口 URL/语义不变；列出计划新增或扩展的 40% 功能（如批量上架、订单筛选等），为每个接口写 API 规范（URL、方法、参数、响应、错误码）。
若添加可选参数或调整 HTTP 方法，更新 doc/*.md 并在测试里覆盖；新增接口同步编写 pytest（可在 fe/test 下增文件/用例）。
如果现有测试脚本不符合新实现，先记录 bug/PR，再在报告里注明以争取加分。
阶段 2：关系数据库设计与建表（满足要求2、报告要求3）

选定 PostgreSQL 或 MySQL；绘制 ER 图，定义实体（users、stores、books、inventories、orders、order_items、user_tokens/logins、payments/logs 等）及字段、主键、外键、唯一约束与索引（如 inventory(store_id, book_id)、orders(status, updated_at)）。
分离大字段（封面、长描述等）至文件/NoSQL，关系表中存引用。
输出建表 SQL 或 ORM 模型 + 初始化脚本（script/init_db.sql 或 Alembic 迁移），确保本地/CI 可一键建库并填充基础数据（含 fe/data/book.db 导入脚本）。
阶段 3：DAO/事务层搭建

新建 be/model/sql_conn.py（或同类模块），加载 DB 配置、建立连接池，并提供 session_scope()／run_in_transaction() 等工具函数。
用 SQLAlchemy/Peewee/原生 SQL 实现基础仓储函数（get_user、create_order、reserve_stock、update_balance 等），返回结构与原 Mongo 版本兼容。
重写 DBConn 为注入 Session/Engine 的基类，所有业务模型继承后通过 DAO 调用数据库，而非直接操作集合。
阶段 4：模块级迁移

迁移顺序：user → seller → buyer → search（依赖逐渐变复杂）。
将每个模块中的 Mongo 查询/更新替换为 DAO/SQL。
对需要一致性的流程（如下单、支付、取消、发货）使用事务封装，处理并发库存/余额。
每迁移完一个模块，运行对应 pytest（test_register.py、test_add_book.py 等）验证行为一致。
若引入新字段（状态时间戳、版本号等），同步更新 schema 与迁移脚本。
阶段 5：数据准备与导入

编写脚本把 fe/data/book.db（SQLite）数据导入新库；若需保留旧 Mongo 测试数据，编写转换脚本。
提供最小可运行数据集初始化逻辑，让测试环境启动前自动创建库、建表、导数据。
阶段 6：测试矩阵与覆盖率（满足要求3）

以 fe/test 为回归基线，针对新增接口和关系型特性补充测试（如并发下单/事务回滚、索引生效、分页准确性）。
继续使用 script/test.sh：coverage run -m pytest … -> coverage report/html；必要时在 pytest.ini 或命令中增加 --cov be --cov-report xml.
保存 coverage report 和 htmlcov 结果，用于报告和成绩证明。
阶段 7：工程实践与版本管理（满足要求4、5、7）

严格使用 git：分支管理、规范 commit message、PR 审查；如可行，尝试 TDD（先写测试再实现）。
在报告中记录所用工程工具（Git/Gitea、CI、pre-commit、格式化、静态分析等）。
强调自主实现：虽然借鉴现有逻辑，但 SQL 版代码需由你们编写，避免“复制原后端”的扣分风险。
阶段 8：接口增强与性能验证（要求1+性能）

在不触碰既有 URL 的前提下，实现新接口（如批量操作、统计、导出），编写说明与测试。
利用 fe/test/test_bench.py 或自写脚本进行性能/并发表现测试，记录数据以支撑报告中“效率合理”。
阶段 9：报告撰写与交付

报告结构参考要求：
文档库→关系库迁移的改动与动机。
对照要求条目说明完成情况（接口扩展、测试、版本控制等，可表格化）。
关系 schema/ER 图、索引、事务策略（包含范式讨论、锁设计）。
60%/40% 功能对应的接口、后端逻辑、数据库操作、测试及结果/覆盖率截图。
亮点展示（高并发控制、缓存、自动化测试、CI、监控等）。
打包“代码 + 报告”，按课程命名规范提交，并附部署/测试说明（如何建库、运行 script/test.sh 等）。
按照这一大纲推进，可覆盖课程的所有关键要求并留下充足的报告素材。如果需要对某个阶段进一步细化（例如 schema 设计或 DAO 模板），随时告诉我。

完成内容总览

关系库重构：所有核心表（users/stores/books/inventories/orders/order_items/book_search_index）升级到 MySQL，DAO + ORM +事务全部重写；BOOKSTORE_DB_URL 现为必填配置，不再 fallback SQLite。Mongo 仅保存 BLOB 与超长文本。
索引/规范化/事务：doc/relational_schema.md、doc/index_design.md、doc/db_best_practices.md 已覆盖 ER→关系模式、3NF 说明、每个表的主外键与索引、以及下单/付款/发货/收货/自动超时的事务策略。
新增 40% 功能+文档：
/seller/batch_add_books：批量上架，多条结果统一返回。
/buyer/orders/export：JSON/CSV 导出，支持过滤/排序。
/search/books_by_image：OCR→全文索引，以 test_pictures/ocr_results.json 缓存 + script/doubao_client.py 接入 Doubao API；fe/test/test_search_by_image.py 做全流程断言。
所有接口说明整理在 doc/api_extensions.md。
OCR工具链：script/export_sample_covers.py、generate_ocr_cache.py、recognize_image_text.py、script/doubao_client.py 搭建图像识别与缓存刷新流程；测试使用缓存，线上可启用真实 API Key。
数据导入/脚本：script/import_books_to_sql.py 将 book_lx.db 写入 MySQL（~4 万行），test_pictures 提供示例封面。
测试与覆盖率：统一用
.\.venv\Scripts\python -m coverage run --timid --branch --source fe,be --concurrency=thread -m pytest -v --ignore=fe/data
全部 61 个 pytest（含 bench、导出、批量、以图搜书）通过，branch coverage ≈87%；coverage report/html 产出在 htmlcov/.
日志/报告素材：app.log、doc/*、生成的 ER/索引图文都可直接引用到最终报告。
下一步建议

整理最终报告：突出 Mongo→MySQL 改动、索引/事务设计、OCR 流程、测试矩阵、覆盖率截图。
若需要演示以图搜书，可使用我提供的脚本输出“每行关键词→匹配书籍”的清单，直观展示识别过程。

61 passed in 307.71s (0:05:07)
(.venv) (base) PS D:\dase\CDMS\大作业二\bookstore> coverage report
Name                               Stmts   Miss Branch BrPart  Cover
--------------------------------------------------------------------
be\__init__.py                         0      0      0      0   100%
be\app.py                              3      3      2      0     0%
be\model\__init__.py                   0      0      0      0   100%
be\model\buyer.py                    190     34     72     17    81%
be\model\dao\__init__.py               0      0      0      0   100%
be\model\dao\order_dao.py             57      7     18      7    81%
be\model\dao\search_dao.py            49      7     20      5    80%
be\model\dao\store_dao.py             36      3      4      0    92%
be\model\dao\user_dao.py              62     17     12      2    72%
be\model\db_conn.py                   14      0      0      0   100%
be\model\error.py                     25      1      0      0    96%
be\model\models.py                    91      0      0      0   100%
be\model\mongo.py                     20      0      0      0   100%
be\model\search.py                    92     30     26      5    67%
be\model\seller.py                   143     28     64     12    80%
be\model\sql_conn.py                  22      4      2      1    79%
be\model\store.py                     10      1      2      1    83%
be\model\user.py                     127     31     32      7    76%
be\serve.py                           43      2      2      0    96%
be\view\__init__.py                    0      0      0      0   100%
be\view\auth.py                       42      0      0      0   100%
be\view\buyer.py                      98     11     10      3    87%
be\view\search.py                     38      6      4      2    81%
be\view\seller.py                     49      0      0      0   100%
fe\__init__.py                         0      0      0      0   100%
fe\access\__init__.py                  0      0      0      0   100%
fe\access\auth.py                     31      0      0      0   100%
fe\access\book.py                    119     36     20      6    68%
fe\access\buyer.py                    76      4     18      4    91%
fe\access\new_buyer.py                 8      0      0      0   100%
fe\access\new_seller.py                8      0      0      0   100%
fe\access\search.py                   12      0      2      0   100%
fe\access\seller.py                   43      0      0      0   100%
fe\bench\__init__.py                   0      0      0      0   100%
fe\bench\run.py                       13      0      6      0   100%
fe\bench\session.py                   47      0     12      2    97%
fe\bench\workload.py                 125      1     20      2    98%
fe\conf.py                            11      0      0      0   100%
fe\conftest.py                        15      0      0      0   100%
fe\test\gen_book_data.py              49      1     16      2    95%
fe\test\test_add_book.py              37      0     10      0   100%
fe\test\test_add_funds.py             23      0      0      0   100%
fe\test\test_add_stock_level.py       40      0     10      0   100%
fe\test\test_bench.py                  6      2      0      0    67%
fe\test\test_buyer_export.py          41      0      2      0   100%
fe\test\test_create_store.py          20      0      0      0   100%
fe\test\test_login.py                 28      0      0      0   100%
fe\test\test_new_order.py             40      0      0      0   100%
fe\test\test_order_edge_cases.py      64      1      4      1    97%
fe\test\test_order_management.py     103      0      0      0   100%
fe\test\test_password.py              33      0      0      0   100%
fe\test\test_payment.py               60      1      4      1    97%
fe\test\test_register.py              31      0      0      0   100%
fe\test\test_search_books.py          60      0      0      0   100%
fe\test\test_search_by_image.py       71      1      6      1    97%
fe\test\test_seller_batch_add.py      42      0      2      0   100%
fe\test\test_shipping_flow.py         43      1      4      1    96%
fe\test\test_user_edge_cases.py       22      0      0      0   100%
--------------------------------------------------------------------
TOTAL                               2532    233    406     82    89%

这些模块的低覆盖率主要来源如下，可以针对性补：

be/model/user.py & be/model/dao/user_dao.py

目前只有 happy-path 的注册/登录/改密用例，错误分支（例如 token 过期、重复注册、软删除恢复、update_token 返回 False）几乎没跑到。
可在 fe/test/test_user_model_errors.py 恢复/新增一些模拟 DAO 异常和错误 token 的测试。
be/model/seller.py / store.py / user.py

许多 return error.xxx 分支和事务回滚没被覆盖。可以在现有卖家测试里增加“非法 store_id、库存不足、DAO 抛异常”的场景，或者用 monkeypatch 模拟 DAO 返回 False。
be/model/search.py

search_books_by_image 的缓存缺失、OCR 抛错、无关键词、兜底 book_id 等分支虽然有接口测试，但覆盖率仍偏低。可以针对这些逻辑写轻量的单元测试，直接调用 Search.search_books_by_image()，用临时图片/字符串构造不同情况。
be/model/sql_conn.py

_get_database_url 抛异常分支和 session_scope 的 rollback 逻辑未走过。可以在单测里临时清除 BOOKSTORE_DB_URL，断言会抛 RuntimeError；再构造一个故意抛异常的 SQL 操作以触发 rollback。
fe/access/book.py

_ensure_seed_data() 中大量逻辑未执行（因为跑测试时已经有 SQLite 文件）。可以写一个独立测试，用临时目录/空数据库去触发建表与 seed；或通过 monkeypatch 清空 book.db 后调用 BookDB()，验证新文件被创建。
fe/test/test_bench.py（覆盖率 67%）

主要是因为里面只有一个 assert 200 == 100 的错误分支。要提高覆盖率，可以再写一些 unit-test 风格的用例直接调用 fe.bench.workload.Workload 的方法，覆盖 get_new_order、update_stat 的分支，或者把 bench 逻辑拆到可测试的函数里。
总的策略：

先挑几个高收益模块（user.py、search.py、fe/access/book.py）补充定向单测，覆盖错误分支和兜底逻辑。
对于 bench/DAO 这类难以在系统测试覆盖的部分，写专门的 unit test，利用 monkeypatch 模拟异常或使用临时数据库。
记得所有新测都要跑 coverage run ... pytest，确保 branch coverage 回到 90% 附近。