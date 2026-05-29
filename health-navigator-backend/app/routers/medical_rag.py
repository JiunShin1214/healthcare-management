from fastapi import APIRouter, HTTPException

from app.schemas.medical_rag import (
    MedicalRagAnswerRequest,
    MedicalRagAnswerResponse,
    MedicalRagCardRequest,
    MedicalRagCardResponse,
    MedicalRagHealthResponse,
    MedicalRagHealthCheckCardRequest,
    MedicalRagHealthCheckCardResponse,
    MedicalRagSearchRequest,
    MedicalRagSearchResponse,
)
from app.services import medical_rag_service


router = APIRouter(
    prefix="/medical-rag",
    tags=["medical-rag"],
)


@router.get(
    "/health",
    response_model=MedicalRagHealthResponse,
    summary="의료 문서 RAG 설정 상태 확인",
)
def check_medical_rag_health():
    return medical_rag_service.medical_rag_health()


@router.post(
    "/search",
    response_model=MedicalRagSearchResponse,
    summary="의료 문서 벡터 검색",
)
def search_medical_documents(req: MedicalRagSearchRequest):
    try:
        documents = medical_rag_service.retrieve_documents(
            query=req.query,
            top_k=req.top_k,
            source=req.source,
            category=req.category,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="의료 문서 검색에 실패했습니다.") from exc
    return {
        "query": req.query,
        "documents": documents,
    }


@router.post(
    "/answer",
    response_model=MedicalRagAnswerResponse,
    summary="의료 문서 근거 기반 답변 생성",
)
def answer_with_medical_rag(req: MedicalRagAnswerRequest):
    try:
        return medical_rag_service.generate_rag_answer(
            question=req.query,
            top_k=req.top_k,
            source=req.source,
            category=req.category,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="의료 RAG 답변 생성에 실패했습니다.") from exc


@router.post(
    "/card",
    response_model=MedicalRagCardResponse,
    summary="의료 문서 근거 기반 참고 카드 생성",
)
def create_medical_rag_card(req: MedicalRagCardRequest):
    try:
        return medical_rag_service.generate_rag_card(
            question=req.query,
            top_k=req.top_k,
            source=req.source,
            category=req.category,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="의료 RAG 카드 생성에 실패했습니다.") from exc


@router.post(
    "/health-check-card",
    response_model=MedicalRagHealthCheckCardResponse,
    summary="건강검진 OCR 결과 기반 참고 카드 생성",
)
def create_health_check_rag_card(req: MedicalRagHealthCheckCardRequest):
    try:
        findings = [finding.model_dump() for finding in req.findings]
        return medical_rag_service.generate_health_check_rag_card(
            parsed_result=req.parsed_result,
            findings=findings,
            top_k=req.top_k,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="건강검진 RAG 카드 생성에 실패했습니다.") from exc
