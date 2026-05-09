from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user

from app.schemas.drug import (
    DrugSearchResponse,
    DrugAutocompleteResponse,
    DrugDetailResponse,
    MedicationCreateRequest,
    MedicationCheckRequest,
    UserMedicationResponse,
    InteractionCheckRequest,
    InteractionCheckResponse,
    DuplicateCheckRequest,
    DuplicateCheckResponse,
)

from app.services import drug_service_db as drug_service


router = APIRouter(
    prefix="/drugs",
    tags=["Drugs"]
)

#기본 약품 목록 조회
@router.get(
    "",
    response_model=list[DrugSearchResponse],
    summary="기본 약품 목록 조회"
)
def get_drug_list(
    limit: int = 20,
    db: Session = Depends(get_db)
):
    return drug_service.get_drug_list(db=db, limit=limit)

# =========================
# 1. 약 검색
# =========================

@router.get(
    "/search",
    response_model=list[DrugSearchResponse],
    summary="약품 검색"
)
def search_drugs(
    q: str,
    db: Session = Depends(get_db)
):
    return drug_service.search_drugs(db=db, q=q)


@router.get(
    "/autocomplete",
    response_model=list[DrugAutocompleteResponse],
    summary="약품 검색 자동완성"
)
def autocomplete_drugs(
    q: str,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    return drug_service.autocomplete_drugs(db=db, q=q, limit=limit)


# =========================
# 2. 직접 병용금기 검사
# =========================

@router.post(
    "/check-interaction",
    response_model=InteractionCheckResponse,
    summary="병용금기 검사"
)
def check_interaction(
    req: InteractionCheckRequest,
    db: Session = Depends(get_db)
):
    return drug_service.check_interaction(
        db=db,
        current_item_seqs=req.currentItemSeqs,
        new_item_seq=req.newItemSeq
    )

# =========================
# 3. 직접 중복복용 검사
# =========================

@router.post(
    "/check-duplicate",
    response_model=DuplicateCheckResponse,
    summary="중복복용 검사"
)
def check_duplicate(
    req: DuplicateCheckRequest,
    db: Session = Depends(get_db)
):
    return drug_service.check_duplicate(
        db=db,
        item_seqs=req.itemSeqs
    )
# =========================
# 4. 내 복용약 목록 조회
# =========================

@router.get(
    "/my-medications",
    response_model=list[UserMedicationResponse],
    summary="내 복용약 목록 조회"
)
def get_my_medications(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return drug_service.get_user_medications(
        db=db,
        user_id=current_user.id
    )


# =========================
# 5. 내 복용약 추가
# =========================

@router.post(
    "/my-medications",
    response_model=UserMedicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="내 복용약 추가"
)
def add_my_medication(
    req: MedicationCreateRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    result = drug_service.add_user_medication(
        db=db,
        user_id=current_user.id,
        item_seq=req.itemSeq,
        memo=req.memo
    )

    if result == "DUPLICATED":
        raise HTTPException(
            status_code=409,
            detail="이미 등록된 복용약입니다."
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="해당 약품을 찾을 수 없습니다."
        )

    return result


# =========================
# 6. 내 복용약 삭제
# =========================

@router.delete(
    "/my-medications/{medication_id}",
    summary="내 복용약 삭제"
)
def delete_my_medication(
    medication_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    success = drug_service.delete_user_medication(
        db=db,
        user_id=current_user.id,
        medication_id=medication_id
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail="복용약 정보를 찾을 수 없습니다."
        )

    return {
        "message": "복용약이 삭제되었습니다."
    }


# =========================
# 7. 내 복용약 + 새 약 병용금기 검사
# =========================

@router.post(
    "/my-medications/check-interaction",
    response_model=InteractionCheckResponse,
    summary="내 복용약 기준 병용금기 검사"
)
def check_my_medication_interaction(
    req: MedicationCheckRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return drug_service.check_my_interaction(
        db=db,
        user_id=current_user.id,
        new_item_seqs=req.itemSeqs
    )

# =========================
# 8. 내 복용약 중복검사
# =========================

@router.post(
    "/my-medications/check-duplicate",
    response_model=DuplicateCheckResponse,
    summary="내 복용약 기준 중복복용 검사"
)
def check_my_medication_duplicate(
    req: MedicationCheckRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return drug_service.check_my_duplicate(
        db=db,
        user_id=current_user.id,
        include_new_item_seqs=req.itemSeqs
    )

# =========================
# 9. 약 상세 조회
# =========================

@router.get(
    "/{item_seq}",
    response_model=DrugDetailResponse,
    summary="약품 상세 조회"
)
def get_drug_detail(
    item_seq: str,
    db: Session = Depends(get_db)
):
    result = drug_service.get_drug_detail(db=db, item_seq=item_seq)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="해당 약품을 찾을 수 없습니다."
        )

    return result
