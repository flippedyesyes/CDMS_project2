import logging
import os
from flask import Flask, Blueprint
from werkzeug.serving import make_server
import threading

from be.view import auth
from be.view import seller
from be.view import buyer
from be.view import search
from be.model.store import init_database, init_completed_event

bp_shutdown = Blueprint("shutdown", __name__)
_stop_event = threading.Event()


def request_shutdown():
    _stop_event.set()


@bp_shutdown.route("/shutdown")
def be_shutdown():
    request_shutdown()
    return "Server shutting down..."


def _create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(bp_shutdown)
    app.register_blueprint(auth.bp_auth)
    app.register_blueprint(seller.bp_seller)
    app.register_blueprint(buyer.bp_buyer)
    app.register_blueprint(search.bp_search)
    return app


def be_run():
    this_path = os.path.dirname(__file__)
    parent_path = os.path.dirname(this_path)
    log_file = os.path.join(parent_path, "app.log")
    init_database(parent_path)

    logging.basicConfig(filename=log_file, level=logging.ERROR)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "%(asctime)s [%(threadName)-12.12s] [%(levelname)-5.5s]  %(message)s"
    )
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)

    app = _create_app()
    server = make_server("127.0.0.1", 5000, app)
    server.timeout = 1
    _stop_event.clear()
    init_completed_event.set()
    while not _stop_event.is_set():
        server.handle_request()
