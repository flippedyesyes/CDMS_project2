from datetime import datetime

from flask import Blueprint, Response, jsonify, request
from be.model.buyer import Buyer

bp_buyer = Blueprint("buyer", __name__, url_prefix="/buyer")


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


@bp_buyer.route("/new_order", methods=["POST"])
def new_order():
    user_id: str = request.json.get("user_id")
    store_id: str = request.json.get("store_id")
    books: [] = request.json.get("books")
    id_and_count = []
    for book in books:
        book_id = book.get("id")
        count = book.get("count")
        id_and_count.append((book_id, count))

    b = Buyer()
    code, message, order_id = b.new_order(user_id, store_id, id_and_count)
    return jsonify({"message": message, "order_id": order_id}), code


@bp_buyer.route("/payment", methods=["POST"])
def payment():
    user_id: str = request.json.get("user_id")
    order_id: str = request.json.get("order_id")
    password: str = request.json.get("password")
    b = Buyer()
    code, message = b.payment(user_id, password, order_id)
    return jsonify({"message": message}), code


@bp_buyer.route("/add_funds", methods=["POST"])
def add_funds():
    user_id = request.json.get("user_id")
    password = request.json.get("password")
    add_value = request.json.get("add_value")
    b = Buyer()
    code, message = b.add_funds(user_id, password, add_value)
    return jsonify({"message": message}), code


@bp_buyer.route("/confirm_receipt", methods=["POST"])
def confirm_receipt():
    user_id = request.json.get("user_id")
    order_id = request.json.get("order_id")
    b = Buyer()
    code, message = b.confirm_receipt(user_id, order_id)
    return jsonify({"message": message}), code


@bp_buyer.route("/cancel_order", methods=["POST"])
def cancel_order():
    user_id = request.json.get("user_id")
    order_id = request.json.get("order_id")
    password = request.json.get("password")
    b = Buyer()
    code, message = b.cancel_order(user_id, password, order_id)
    return jsonify({"message": message}), code


@bp_buyer.route("/orders", methods=["GET"])
def list_orders():
    user_id = request.args.get("user_id")
    status = request.args.get("status")
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.args.get("page_size", 20))
    except (TypeError, ValueError):
        page_size = 20
    created_from = _parse_time(request.args.get("created_from"))
    created_to = _parse_time(request.args.get("created_to"))
    sort_by = request.args.get("sort_by", "updated_at")
    b = Buyer()
    code, message, payload = b.list_orders(
        user_id, status, page, page_size, created_from, created_to, sort_by
    )
    response = {"message": message}
    if code == 200:
        response.update(payload)
    return jsonify(response), code


@bp_buyer.route("/orders/export", methods=["GET"])
def export_orders():
    user_id = request.args.get("user_id")
    status = request.args.get("status")
    sort_by = request.args.get("sort_by", "updated_at")
    fmt = (request.args.get("format") or "json").lower()
    try:
        limit = int(request.args.get("limit", 500))
    except (TypeError, ValueError):
        limit = 500
    created_from = _parse_time(request.args.get("created_from"))
    created_to = _parse_time(request.args.get("created_to"))

    b = Buyer()
    code, message, data = b.export_orders(
        user_id=user_id,
        status=status,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        fmt=fmt,
        limit=limit,
    )
    if code != 200 or data is None:
        return jsonify({"message": message}), code
    if fmt == "csv":
        content = data.get("content", "")
        response = Response(content, mimetype="text/csv")
        response.headers["Content-Disposition"] = "attachment; filename=orders.csv"
        return response
    return jsonify({"message": message, "orders": data.get("orders", [])}), 200
