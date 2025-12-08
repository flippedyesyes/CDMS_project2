import base64
import mimetypes
import os
from typing import Optional

import requests

API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
MODEL_NAME = "doubao-seed-1-6-251015"
PROMPT_TEMPLATE = """你是一位专业的图像文字识别员，擅长准确识别各类图片中的文字内容。你的任务是识别指定图片中的所有文字，并直接输出识别结果。

输入图片: {image_path}

任务要求:
1. 对图片中的所有可见文字进行完整、准确的识别
2. 严格按照文字在图片中的顺序输出识别结果
3. 输出内容仅包含识别到的文字，不添加任何解释、说明或额外内容
4. 若图片中无可见文字，则输出空字符串

输出格式:
请直接输出识别到的文字内容。
"""


class DoubaoError(RuntimeError):
    pass


def _build_image_url(path_or_url: str) -> str:
    if path_or_url.lower().startswith(("http://", "https://")):
        return path_or_url
    if not os.path.isfile(path_or_url):
        raise FileNotFoundError(f"image not found: {path_or_url}")
    mime, _ = mimetypes.guess_type(path_or_url)
    mime = mime or "image/jpeg"
    with open(path_or_url, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime};base64,{encoded}"


def recognize_image_text(path_or_url: str, api_key: Optional[str] = None) -> str:
    token = api_key or os.getenv("DOUBAO_API_KEY")
    if not token:
        raise DoubaoError("DOUBAO_API_KEY is not set")

    image_url = _build_image_url(path_or_url)
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_url}},
                    {
                        "type": "text",
                        "text": PROMPT_TEMPLATE.format(image_path=path_or_url),
                    },
                ],
            }
        ],
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    response = requests.post(API_URL, headers=headers, json=payload, timeout=60)
    if response.status_code != 200:
        raise DoubaoError(
            f"API error {response.status_code}: {response.text}"
        )
    data = response.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DoubaoError(f"unexpected response: {data}") from exc

    def _slice_text(text: str) -> str:
        marker = "reasoning_content"
        if marker in text:
            text = text.split(marker, 1)[0]
        return text.strip()

    if isinstance(content, str):
        return _slice_text(content)
    if isinstance(content, list):
        texts = []
        for part in content:
            if isinstance(part, dict):
                value = part.get("text")
                if isinstance(value, str):
                    texts.append(_slice_text(value))
        if texts:
            return "\n".join(filter(None, texts)).strip()
    raise DoubaoError(f"unexpected response: {data}")
