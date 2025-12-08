import os
import random
from pathlib import Path
from typing import Iterable, Optional

from bson.binary import Binary

from be.model.mongo import get_book_collection

DEFAULT_DEST = Path("test_pictures")


def _save_picture(book_id: str, picture, dest: Path) -> Optional[Path]:
    if not picture:
        return None
    if isinstance(picture, Binary):
        data = bytes(picture)
    elif isinstance(picture, (bytes, bytearray)):
        data = bytes(picture)
    else:
        # assume base64 encoded string
        import base64

        data = base64.b64decode(picture)

    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{book_id}.jpg"
    with open(path, "wb") as f:
        f.write(data)
    return path


def export_sample_covers(
    book_ids: Optional[Iterable[str]] = None,
    limit: int = 10,
    dest: Path = DEFAULT_DEST,
) -> None:
    coll = get_book_collection()
    dest.mkdir(parents=True, exist_ok=True)

    docs = []
    if book_ids:
        docs = list(
            coll.find(
                {
                    "doc_type": "book_blob",
                    "book_id": {"$in": list(book_ids)},
                    "picture": {"$exists": True},
                }
            )
        )
    else:
        docs = list(
            coll.aggregate(
                [
                    {"$match": {"doc_type": "book_blob", "picture": {"$exists": True}}},
                    {"$sample": {"size": limit}},
                ]
            )
        )

    for doc in docs[:limit]:
        book_id = doc.get("book_id")
        pic = doc.get("picture")
        if not book_id or not pic:
            continue
        _save_picture(book_id, pic, dest)


def main():
    dest = Path(os.environ.get("BOOKSTORE_PICTURE_DIR", DEFAULT_DEST))
    export_sample_covers(dest=dest)
    print(f"Exported sample covers into {dest.resolve()}")


if __name__ == "__main__":
    main()
