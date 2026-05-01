import json
import time
import requests
from app.core.config import CLOVA_OCR_INVOKE_URL, CLOVA_OCR_SECRET_KEY


def call_clova_ocr(file_bytes: bytes, filename: str) -> dict:
    ext = filename.split(".")[-1].lower()

    headers = {
        "X-OCR-SECRET": CLOVA_OCR_SECRET_KEY
    }

    request_json = {
        "images": [
            {
                "format": ext,
                "name": "demo"
            }
        ],
        "requestId": str(int(time.time() * 1000)),
        "version": "V2",
        "timestamp": int(time.time() * 1000)
    }

    payload = {
        "message": json.dumps(request_json).encode("UTF-8")
    }

    files = [
        ("file", (filename, file_bytes))
    ]

    response = requests.post(
        CLOVA_OCR_INVOKE_URL,
        headers=headers,
        data=payload,
        files=files,
        timeout=30
    )

    response.raise_for_status()

    try:
        return response.json()
    except Exception as e:
        raise ValueError(f"OCR 응답 JSON 파싱 실패: {e}")