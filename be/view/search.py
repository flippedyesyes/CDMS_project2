from flask import Blueprint, jsonify, request

from be.model.search import Search

bp_search = Blueprint("search", __name__, url_prefix="/search")


@bp_search.route("/books", methods=["GET"])
def search_books():
    keyword = request.args.get("q", "")
    store_id = request.args.get("store_id")
    try:
        page = int(request.args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.args.get("page_size", 20))
    except (TypeError, ValueError):
        page_size = 20

    s = Search()
    code, message, payload = s.search_books(keyword, store_id, page, page_size)
    response = {"message": message}
    if code == 200:
        response.update(payload)
    return jsonify(response), code


@bp_search.route("/books_by_image", methods=["POST"])
def search_books_by_image():
    data = request.json or {}
    image_path = data.get("image_path")
    store_id = data.get("store_id")
    override_text = data.get("ocr_text")
    override_book_id = data.get("book_id")
    try:
        page_size = int(data.get("page_size", 10))
    except (TypeError, ValueError):
        page_size = 10

    s = Search()
    code, message, payload = s.search_books_by_image(
        image_path=image_path,
        store_id=store_id,
        page_size=page_size,
        override_text=override_text,
        override_book_id=override_book_id,
    )
    response = {"message": message}
    if payload:
        response.update(payload)
    return jsonify(response), code


@bp_search.route("/recommend_by_tags", methods=["POST"])
def recommend_by_tags():
    data = request.json or {}
    tags = data.get("tags") or []
    store_id = data.get("store_id")
    try:
        limit = int(data.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10

    if isinstance(tags, str):
        tags = [tags]

    s = Search()
    code, message, payload = s.recommend_by_tags(tags=tags, store_id=store_id, limit=limit)
    response = {"message": message}
    if payload:
        response.update(payload)
    return jsonify(response), code
