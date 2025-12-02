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
