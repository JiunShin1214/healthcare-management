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


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default

CLOVA_OCR_INVOKE_URL = os.getenv("CLOVA_OCR_INVOKE_URL")
CLOVA_OCR_SECRET_KEY = os.getenv("CLOVA_OCR_SECRET_KEY")
SYMPTOM_STRUCTURE_PROVIDER_ENABLED = _env_bool("SYMPTOM_STRUCTURE_PROVIDER_ENABLED", False)
SYMPTOM_STRUCTURE_PROVIDER_NAME = os.getenv("SYMPTOM_STRUCTURE_PROVIDER_NAME", "none")
SYMPTOM_STRUCTURE_MODEL_ID = os.getenv("SYMPTOM_STRUCTURE_MODEL_ID", "")
SYMPTOM_STRUCTURE_TIMEOUT_MS = _env_int("SYMPTOM_STRUCTURE_TIMEOUT_MS", 2000)
MEDICAL_BERT_STRUCTURE_ENABLED = _env_bool("MEDICAL_BERT_STRUCTURE_ENABLED", False)
MEDICAL_BERT_MODEL_DIR = os.getenv("MEDICAL_BERT_MODEL_DIR", "C:/tmp/health-navigator-models/kmbert-structure")
MEDICAL_BERT_MODEL_ID = os.getenv("MEDICAL_BERT_MODEL_ID", "")
MEDICAL_BERT_SCORE_THRESHOLD = _env_float("MEDICAL_BERT_SCORE_THRESHOLD", 0.5)
RAG_VECTOR_SEARCH_ENABLED = _env_bool("RAG_VECTOR_SEARCH_ENABLED", True)
RAG_EMBEDDING_MODEL_NAME = os.getenv(
    "RAG_EMBEDDING_MODEL_NAME",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
RAG_EMBEDDING_CACHE_DIR = os.getenv("RAG_EMBEDDING_CACHE_DIR", "")

if not CLOVA_OCR_INVOKE_URL or not CLOVA_OCR_SECRET_KEY:
    raise ValueError("CLOVA OCR 환경변수가 설정되지 않았습니다.")
