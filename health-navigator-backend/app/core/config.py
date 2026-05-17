from dotenv import load_dotenv
import os

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default

CLOVA_OCR_INVOKE_URL = os.getenv("CLOVA_OCR_INVOKE_URL")
CLOVA_OCR_SECRET_KEY = os.getenv("CLOVA_OCR_SECRET_KEY")
SYMPTOM_STRUCTURE_PROVIDER_ENABLED = _env_bool("SYMPTOM_STRUCTURE_PROVIDER_ENABLED", False)
SYMPTOM_STRUCTURE_PROVIDER_NAME = os.getenv("SYMPTOM_STRUCTURE_PROVIDER_NAME", "none")
SYMPTOM_STRUCTURE_MODEL_ID = os.getenv("SYMPTOM_STRUCTURE_MODEL_ID", "")
SYMPTOM_STRUCTURE_TIMEOUT_MS = _env_int("SYMPTOM_STRUCTURE_TIMEOUT_MS", 2000)

if not CLOVA_OCR_INVOKE_URL or not CLOVA_OCR_SECRET_KEY:
    raise ValueError("CLOVA OCR 환경변수가 설정되지 않았습니다.")
