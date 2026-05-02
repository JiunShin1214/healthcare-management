from fastapi import APIRouter, UploadFile, File, HTTPException
import traceback

from app.schemas.health_check import HealthCheckResponse
from app.services.ocr_service import call_clova_ocr
from app.services.text_reconstructor import reconstruct_text_from_ocr_result
from app.services.parser_service import parse_health_checkup

router = APIRouter()


@router.post("/ocr", response_model=HealthCheckResponse)
async def upload_health_check(file: UploadFile = File(...)):
    allowed_ext = {"jpg", "jpeg", "png", "pdf"}

    if not file.filename or "." not in file.filename:
        raise HTTPException(status_code=400, detail="파일명이 올바르지 않습니다.")

    ext = file.filename.split(".")[-1].lower()

    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다.")

    stage = "start"

    try:
        stage = "read_file"
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(status_code=400, detail="업로드된 파일이 비어 있습니다.")

        stage = "call_ocr"
        ocr_result = call_clova_ocr(file_bytes, file.filename)
        print("OCR RESULT TYPE:", type(ocr_result))
        print("OCR RESULT IS NONE:", ocr_result is None)

        if not isinstance(ocr_result, dict):
            raise HTTPException(
                status_code=502,
                detail=f"OCR API 응답이 올바르지 않습니다. type={type(ocr_result)}"
            )

        stage = "reconstruct_text"
        extracted_text = reconstruct_text_from_ocr_result(ocr_result)
        print("EXTRACTED TEXT TYPE:", type(extracted_text))
        print("EXTRACTED TEXT PREVIEW:", extracted_text[:300] if isinstance(extracted_text, str) else extracted_text)

        if not isinstance(extracted_text, str) or not extracted_text.strip():
            raise HTTPException(
                status_code=502,
                detail="OCR 결과에서 텍스트를 추출하지 못했습니다."
            )

        stage = "parse_health_checkup"
        parsed = parse_health_checkup(extracted_text)
        print("PARSED TYPE:", type(parsed))

        if not isinstance(parsed, dict):
            raise HTTPException(
                status_code=500,
                detail="파싱 결과가 dict가 아닙니다."
            )

        return HealthCheckResponse(
            message="health check parsed successfully",
            extracted_text=extracted_text,
            parsing_status=parsed.get("parsing_status"),
            missing_fields=parsed.get("missing_fields", []),
            data=parsed
        )

    except HTTPException:
        raise

    except Exception as e:
        print("ERROR STAGE:", stage)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"OCR/파싱 처리 실패 단계={stage}: {str(e)}"
        )