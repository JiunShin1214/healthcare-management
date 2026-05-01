from dotenv import load_dotenv
import os

load_dotenv()

CLOVA_OCR_INVOKE_URL = os.getenv("CLOVA_OCR_INVOKE_URL")
CLOVA_OCR_SECRET_KEY = os.getenv("CLOVA_OCR_SECRET_KEY")

if not CLOVA_OCR_INVOKE_URL or not CLOVA_OCR_SECRET_KEY:
    raise ValueError("CLOVA OCR 환경변수가 설정되지 않았습니다.")