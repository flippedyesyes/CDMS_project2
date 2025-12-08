import argparse

from be.util.doubao_client import DoubaoError, recognize_image_text


def main():
    parser = argparse.ArgumentParser(
        description="Recognize text from an image using ByteDance Doubao API."
    )
    parser.add_argument("image", help="Local image path or HTTP(S) URL")
    parser.add_argument(
        "--api-key",
        dest="api_key",
        help="Override DOUBAO_API_KEY environment variable",
    )
    args = parser.parse_args()

    try:
        text = recognize_image_text(args.image, api_key=args.api_key)
        print(text)
    except DoubaoError as exc:
        raise SystemExit(f"Recognition failed: {exc}")


if __name__ == "__main__":
    main()
