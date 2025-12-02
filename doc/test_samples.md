 * Serving Flask app 'be.serve' (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
- 搜索 search

  | 测试情况 | 传参 | 结果 message |
  | --- | --- | --- |
  | 分页查询 | ("三毛", 0) | PASS (code=200, total=8) |
  | 全部显示查询 | ("三毛", 1) | PASS (code=200, total=8) |
  | 不存在的关键词 | ("三毛+", 1) | PASS (code=200, total=0) |
  | 空页 | ("三毛", 1000) | PASS (code=200, total=8) |
  | 不存在的关键词 + 空页 | ("三毛+", 1000) | PASS (code=200, total=0) |

  - 多关键词搜索

  | 测试情况 | 传参 | 结果 message |
  | --- | --- | --- |
  | 查询成功 | ["三毛", "袁氏"] | PASS (code=200, total=8) |
  | 查询成功（含额外关键字） | ["三毛", "袁氏", "心灵"] | PASS (code=200, total=8) |
  | 含不存在的关键词查询 | ["三毛", "袁氏++"] | PASS (code=200, total=8) |
  | 不存在关键词 | ["三毛++", "袁氏++"] | PASS (code=200, total=0) |

- 发货 send_books

  | 测试情况 | 传参 | 结果 message |
  | --- | --- | --- |
  | 付款后发货成功 | (store_id, order_id) | PASS (new=200, pay=200, ship=200) |
  | 未付款无法发货 | (store_id, 未付款 order_id) | PASS (new=200, ship=520) |
  | 发货不存在的书 | (store_id, 错误 book_id) | PASS (ship=518, order=missing-0b8ec977-452c-45e9-b27c-f30095f026f6) |
  | 发货不存在的订单 | (store_id, 错误 order_id) | PASS (ship=518, order=missing-a0441daa-9cd4-4c1a-940c-d427748a76c9) |
  | 店铺不存在 | (错误 store_id, order_id) | PASS (new=200, pay=200, ship=513) |

- 收货 receive_books

  | 测试情况 | 传参 | 结果 message |
  | --- | --- | --- |
  | 付款成功且发货成功后收货 | (buyer_id, password, order_id) | PASS (new=200, pay=200, ship=200, confirm=200) |
  | 未付款订单 | (buyer_id, 错误状态 order_id) | PASS (new=200, confirm=520) |
  | 买家不存在 | (不存在的 buyer_id) | PASS (http_code=401) |
  | 订单不存在 | (buyer_id, 不存在的 order_id) | PASS (confirm=518) |

- 买家查询历史订单

  | 测试情况 | 传参 | 结果 message |
  | --- | --- | --- |
  | 下单后查询历史订单，空 | (buyer_id) | PASS (code=200, total=0) |
  | 发货后查询历史订单，空 | (buyer_id) | PASS (code=200, total=0) |
  | 收货后查询历史订单 | (buyer_id) | PASS (code=200, total=1) |

- 买家查询当前订单

  | 测试情况 | 传参 | 结果 message |
  | --- | --- | --- |
  | 下单后查询当前订单 | (buyer_id) | PASS (code=200, total=1) |
  | 发货后查询当前订单 | (buyer_id) | PASS (code=200, total=1) |
  | 收货后查询当前订单，为空 | (buyer_id) | PASS (code=200, total=0) |
