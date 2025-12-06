import requests
import simplejson
from urllib.parse import urljoin
from fe.access.auth import Auth


class Buyer:
    def __init__(self, url_prefix, user_id, password):
        self.url_prefix = urljoin(url_prefix, "buyer/")
        self.user_id = user_id
        self.password = password
        self.token = ""
        self.terminal = "my terminal"
        self.auth = Auth(url_prefix)
        code, self.token = self.auth.login(self.user_id, self.password, self.terminal)
        assert code == 200

    def new_order(self, store_id: str, book_id_and_count: [(str, int)]) -> (int, str):
        books = []
        for id_count_pair in book_id_and_count:
            books.append({"id": id_count_pair[0], "count": id_count_pair[1]})
        json = {"user_id": self.user_id, "store_id": store_id, "books": books}
        # print(simplejson.dumps(json))
        url = urljoin(self.url_prefix, "new_order")
        headers = {"token": self.token}
        r = requests.post(url, headers=headers, json=json)
        response_json = r.json()
        return r.status_code, response_json.get("order_id")

    def payment(self, order_id: str):
        json = {
            "user_id": self.user_id,
            "password": self.password,
            "order_id": order_id,
        }
        url = urljoin(self.url_prefix, "payment")
        headers = {"token": self.token}
        r = requests.post(url, headers=headers, json=json)
        return r.status_code

    def add_funds(self, add_value: str) -> int:
        json = {
            "user_id": self.user_id,
            "password": self.password,
            "add_value": add_value,
        }
        url = urljoin(self.url_prefix, "add_funds")
        headers = {"token": self.token}
        r = requests.post(url, headers=headers, json=json)
        return r.status_code

    def confirm_receipt(self, order_id: str) -> int:
        json = {
            "user_id": self.user_id,
            "order_id": order_id,
        }
        url = urljoin(self.url_prefix, "confirm_receipt")
        headers = {"token": self.token}
        r = requests.post(url, headers=headers, json=json)
        return r.status_code

    def cancel_order(self, order_id: str, password: str = None):
        json = {"user_id": self.user_id, "order_id": order_id}
        if password is not None:
            json["password"] = password
        url = urljoin(self.url_prefix, "cancel_order")
        headers = {"token": self.token}
        r = requests.post(url, headers=headers, json=json)
        return r.status_code, r.json()

    def list_orders(
        self,
        status: str = "",
        page: int = 1,
        page_size: int = 20,
        created_from: str = "",
        created_to: str = "",
        sort_by: str = "updated_at",
    ) -> (int, dict):
        params = {
            "user_id": self.user_id,
            "page": page,
            "page_size": page_size,
            "sort_by": sort_by,
        }
        if status:
            params["status"] = status
        if created_from:
            params["created_from"] = created_from
        if created_to:
            params["created_to"] = created_to
        url = urljoin(self.url_prefix, "orders")
        headers = {"token": self.token}
        r = requests.get(url, headers=headers, params=params)
        return r.status_code, r.json()

    def export_orders(
        self,
        status: str = "",
        created_from: str = "",
        created_to: str = "",
        sort_by: str = "updated_at",
        fmt: str = "json",
        limit: int = 500,
    ):
        params = {
            "user_id": self.user_id,
            "format": fmt,
            "sort_by": sort_by,
            "limit": limit,
        }
        if status:
            params["status"] = status
        if created_from:
            params["created_from"] = created_from
        if created_to:
            params["created_to"] = created_to
        url = urljoin(self.url_prefix, "orders/export")
        headers = {"token": self.token}
        r = requests.get(url, headers=headers, params=params)
        if fmt == "csv":
            return r.status_code, r.text
        return r.status_code, r.json()
