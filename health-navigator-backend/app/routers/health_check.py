from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.health_check import HealthCheckResponse
from app.services.ocr_service import call_clova_ocr
from app.services.text_reconstructor import reconstruct_text_from_ocr_result
from app.services.parser_service import parse_health_checkup

router = APIRouter()


@router.post("/ocr", response_model=HealthCheckResponse)
async def upload_health_check(file: UploadFile = File(...)):
    allowed_ext = {"jpg", "jpeg", "png", "pdf"}
    ext = file.filename.split(".")[-1].lower()

    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="지원하지 않는 파일 형식입니다.")

    try:
        file_bytes = await file.read()
        ocr_result = call_clova_ocr(file_bytes, file.filename)
        extracted_text = reconstruct_text_from_ocr_result(ocr_result)
        parsed = parse_health_checkup(extracted_text)

        return HealthCheckResponse(
            message="health check parsed successfully",
            extracted_text=extracted_text,
            parsing_status=parsed.get("parsing_status"),
            missing_fields=parsed.get("missing_fields", []),
            data=parsed
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR/파싱 처리 실패: {str(e)}")

