from fastapi import APIRouter, Depends, HTTPException

from app.routers.auth import get_current_user
from app.schemas.symptom_checker import (
    AuthenticatedSymptomAssessRequest,
    BodyRegionResponse,
    BodyRegionSymptomResponse,
    ContextGuideResponse,
    ContextOptionResponse,
    SymptomExplainRequest,
    SymptomExplainResponse,
    SymptomAssessRequest,
    SymptomAssessResponse,
    SymptomStructureRequest,
    SymptomStructureResponse,
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


@router.get(
    "/body-regions/{region_id}/context-guide",
    response_model=ContextGuideResponse,
    summary="부위별 사용자 컨텍스트 입력 가이드 조회",
)
def get_region_context_guide(region_id: str):
    result = symptom_checker_service.get_context_guide(region_id)
    if result is None:
        raise HTTPException(status_code=404, detail="해당 부위를 찾을 수 없습니다.")
    return result


@router.post(
    "/structure",
    response_model=SymptomStructureResponse,
    summary="서술형 입력 구조화 후보 검증",
)
def structure_symptom_input(req: SymptomStructureRequest):
    return symptom_checker_service.structure_symptom_input(req)


@router.post(
    "/explain",
    response_model=SymptomExplainResponse,
    summary="증상 평가 결과 안전 설명 카드 조회",
)
def explain_symptom_assessment(req: SymptomExplainRequest):
    return symptom_checker_service.explain_symptom_assessment(req)


@router.post(
    "/assess",
    response_model=SymptomAssessResponse,
    summary="증상 기반 질환 후보 조회",
)
def assess_symptoms(req: SymptomAssessRequest):
    try:
        result = symptom_checker_service.assess_symptoms(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="해당 부위를 찾을 수 없습니다.")
    return result


@router.post(
    "/assess/me",
    response_model=SymptomAssessResponse,
    summary="로그인 사용자 정보로 증상 기반 질환 후보 조회",
)
def assess_my_symptoms(req: AuthenticatedSymptomAssessRequest, current_user=Depends(get_current_user)):
    enriched_request = SymptomAssessRequest(
        **req.model_dump(),
        gender=current_user.gender,
        birth_date=current_user.birth_date,
    )
    try:
        result = symptom_checker_service.assess_symptoms(
            enriched_request,
            profile_source="authenticated_user",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="해당 부위를 찾을 수 없습니다.")
    return result
