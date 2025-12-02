import requests
from urllib.parse import urljoin


class Search:
    def __init__(self, url_prefix):
        self.url_prefix = urljoin(url_prefix, "search/")

    def books(
        self,
        keyword: str,
        store_id: str = "",
        page: int = 1,
        page_size: int = 20,
    ):
        params = {
            "q": keyword,
            "page": page,
            "page_size": page_size,
        }
        if store_id:
            params["store_id"] = store_id
        url = urljoin(self.url_prefix, "books")
        r = requests.get(url, params=params)
        return r.status_code, r.json()
