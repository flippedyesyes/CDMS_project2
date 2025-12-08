import argparse
import json
import os
from pathlib import Path
from typing import Dict

from be.model.models import Book
from be.model.sql_conn import session_scope
from script.doubao_client import DoubaoError, recognize_image_text

DEFAULT_DIR = Path("test_pictures")
DEFAULT_OUTPUT = DEFAULT_DIR / "ocr_results.json"


def load_existing(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {row["book_id"]: row for row in data}


def main():
    parser = argparse.ArgumentParser(
        description="Run OCR on sample cover images and cache the results."
    )
    parser.add_argument(
        "--image-dir",
        type=Path,
        default=DEFAULT_DIR,
        help="Directory containing sample cover images",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output JSON file for OCR results",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-run OCR even if a book_id already exists in the cache",
    )
    args = parser.parse_args()

    image_dir: Path = args.image_dir
    output: Path = args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    existing = load_existing(output)
    results = []

    for image_path in sorted(image_dir.glob("*.jpg")):
        book_id = image_path.stem
        if not args.overwrite and book_id in existing:
            results.append(existing[book_id])
            continue
        try:
            text = recognize_image_text(str(image_path))
            source = "ocr"
        except DoubaoError as exc:
            print(f"OCR failed for {image_path}: {exc}")
            text = ""
            source = "error"
        if not text:
            with session_scope() as session:
                book = session.get(Book, book_id)
                if book:
                    parts = [
                        book.title or "",
                        book.author or "",
                        book.publisher or "",
                    ]
                    fallback = " ".join(part for part in parts if part)
                    if fallback:
                        text = fallback
                        source = "fallback"
        result = {
            "book_id": book_id,
            "image_path": str(image_path),
            "ocr_text": text,
            "source": source,
        }
        results.append(result)
        print(f"{book_id}: {text[:60]}")

    with output.open("w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved OCR cache to {output}")


if __name__ == "__main__":
    if not os.getenv("DOUBAO_API_KEY"):
        raise SystemExit("Please set DOUBAO_API_KEY environment variable before running.")
    main()
