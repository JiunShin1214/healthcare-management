from fastapi import APIRouter, HTTPException

from app.schemas.symptom_checker import (
    BodyRegionResponse,
    BodyRegionSymptomResponse,
    ContextOptionResponse,
    SymptomAssessRequest,
    SymptomAssessResponse,
)
from app.services import symptom_checker_service


router = APIRouter(
    prefix="/symptom-checker",
    tags=["symptom-checker"],
)


@router.get(
    "/body-regions",
    response_model=list[BodyRegionResponse],
    summary="인체 큰 부위 목록 조회",
)
def get_body_regions():
    return symptom_checker_service.get_body_regions()


@router.get(
    "/contexts",
    response_model=list[ContextOptionResponse],
    summary="증상 평가에 사용할 컨텍스트 선택지 조회",
)
def get_context_options():
    return symptom_checker_service.get_context_options()


@router.get(
    "/body-regions/{region_id}/symptoms",
    response_model=BodyRegionSymptomResponse,
    summary="부위별 세부 부위와 증상 선택지 조회",
)
def get_region_symptoms(region_id: str):
    result = symptom_checker_service.get_region_options(region_id)
    if result is None:
        raise HTTPException(status_code=404, detail="해당 부위를 찾을 수 없습니다.")
    return result


@router.post(
    "/assess",
    response_model=SymptomAssessResponse,
    summary="증상 기반 질환 후보 조회",
)
def assess_symptoms(req: SymptomAssessRequest):
    result = symptom_checker_service.assess_symptoms(req)
    if result is None:
        raise HTTPException(status_code=404, detail="해당 부위를 찾을 수 없습니다.")
    return result
