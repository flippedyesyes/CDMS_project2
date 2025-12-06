# 现有接口清单（60% 功能）

## Auth
- `POST /auth/register`：注册，body 包含 `user_id`, `password`。
- `POST /auth/unregister`：注销，body 包含 `user_id`, `password`。
- `POST /auth/login`：登录并获取 token，body 包含 `user_id`, `password`, `terminal`。
- `POST /auth/logout`：登出，请求头携带 `token`，body 含 `user_id`。
- `POST /auth/password`：修改密码，body 包含 `user_id`, `oldPassword`, `newPassword`。

## Seller
- `POST /seller/create_store`：创建店铺，`user_id`, `store_id`。
- `POST /seller/add_book`：上架图书，`user_id`, `store_id`, `book_info`, `stock_level`。
- `POST /seller/add_stock_level`：补货，`user_id`, `store_id`, `book_id`, `add_stock_level`。
- `POST /seller/ship_order`：发货，`user_id`, `store_id`, `order_id`。

## Buyer
- `POST /buyer/new_order`：下单，`user_id`, `store_id`, `books[{id,count}]`。
- `POST /buyer/payment`：付款，`user_id`, `order_id`, `password`。
- `POST /buyer/add_funds`：充值，`user_id`, `password`, `add_value`。
- `POST /buyer/cancel_order`：取消订单，`user_id`, `order_id`, `password?`。
- `POST /buyer/confirm_receipt`：确认收货，`user_id`, `order_id`。
- `GET /buyer/orders`：订单查询，query `user_id`, `status?`, `page?`, `page_size?`。

## Search
- `GET /search/books`：图书搜索，query `q?`, `store_id?`, `page?`, `page_size?`。

> 以上 URL/方法即 60% 基础测试所依赖的现有接口。在 Lab2 中必须保持兼容，只能增加可选参数或新增并列接口。
