import argparse
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List

from bson.binary import Binary
from pymongo import MongoClient

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[1] / "fe" / "data" / "book_lx.db"
DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_DB = "bookstore"
DEFAULT_COLLECTION = "booklx"
DEFAULT_BATCH_SIZE = 1000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="将 SQLite book_lx 数据导入 MongoDB（可定制路径/集合）"
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=DEFAULT_SQLITE_PATH,
        help=f"SQLite 文件路径（默认 {DEFAULT_SQLITE_PATH}）",
    )
    parser.add_argument("--mongo-uri", default=DEFAULT_MONGO_URI, help="MongoDB 连接 URI")
    parser.add_argument("--db", default=DEFAULT_DB, help="MongoDB 数据库名")
    parser.add_argument("--collection", default=DEFAULT_COLLECTION, help="目标集合名")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="批量写入大小",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="保留集合现有数据（默认会 drop 后重建）",
    )
    return parser.parse_args()


def row_to_doc(row: Iterable, columns: List[str]) -> Dict:
    doc = dict(zip(columns, row))
    picture = doc.get("picture")
    if picture is not None:
        doc["picture"] = Binary(picture)  # 若想保存成字符串，可改为 base64.b64encode()
    return doc


def main() -> None:
    args = parse_args()
    sqlite_path = args.sqlite_path.expanduser()
    if not sqlite_path.exists():
        raise SystemExit(f"找不到 SQLite 文件：{sqlite_path}")

    client = MongoClient(args.mongo_uri)
    db = client[args.db]
    coll = db[args.collection]
    if not args.keep_existing:
        coll.drop()  # 重新导入时清空集合；生产环境慎用

    conn = sqlite3.connect(str(sqlite_path))
    conn.row_factory = sqlite3.Row

    try:
        cur = conn.execute("SELECT * FROM book")
        columns = [c[0] for c in cur.description]
        batch = []
        inserted = 0

        for row in cur:
            batch.append(row_to_doc(row, columns))
            if len(batch) >= args.batch_size:
                coll.insert_many(batch, ordered=False)
                inserted += len(batch)
                batch.clear()

        if batch:
            coll.insert_many(batch, ordered=False)
            inserted += len(batch)

        print(
            f"Inserted {inserted} documents into {args.db}.{args.collection} "
            f"from {sqlite_path}"
        )
    finally:
        conn.close()
        client.close()


if __name__ == "__main__":
    main()
