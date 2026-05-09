from pydantic import BaseModel
from typing import List, Optional


# =========================
# 약 검색
# =========================

class DrugSearchResponse(BaseModel):
    itemSeq: str
    itemName: str
    entpName: Optional[str] = ""
    ingredientName: Optional[str] = ""
    ingredientCount: Optional[str] = ""
    productType: Optional[str] = ""
    etcOtc: Optional[str] = ""
    imageUrl: Optional[str] = ""


class DrugAutocompleteResponse(BaseModel):
    itemSeq: str
    itemName: str
    entpName: Optional[str] = ""


# =========================
# 약 상세 조회
# =========================

class DrugDetailResponse(BaseModel):
    itemSeq: str
    itemName: str = ""
    itemEngName: str = ""
    entpName: str = ""
    ingredient: str = ""
    productType: str = ""
    etcOtc: str = ""
    imageUrl: str = ""

    chart: str = ""
    storage: str = ""

    effect: str = ""
    useMethod: str = ""
    warning: str = ""
    sideEffect: str = ""

    ediCode: str = ""
    atcCode: str = ""
    packUnit: str = ""
    cancelName: str = ""
    permitDate: str = ""

    hasMedicationInfo: bool = False
    missingInfoFields: List[str] = []


# =========================
# 사용자 복용약
# =========================

class MedicationCreateRequest(BaseModel):
    itemSeq: str
    memo: Optional[str] = ""

class MedicationCheckRequest(BaseModel):
    itemSeqs: List[str] = []

class UserMedicationResponse(BaseModel):
    id: int
    itemSeq: str
    itemName: str = ""
    entpName: str = ""
    memo: Optional[str] = ""
    createdAt: Optional[str] = ""


# =========================
# 병용금기 검사
# =========================

class InteractionCheckRequest(BaseModel):
    currentItemSeqs: List[str]
    newItemSeq: str


class InteractionResult(BaseModel):
    source: str = ""
    type: str = ""
    drugASeq: str = ""
    drugAName: str = ""
    ingredientA: str = ""
    drugBSeq: str = ""
    drugBName: str = ""
    ingredientB: str = ""
    reason: str = ""


class InteractionCheckResponse(BaseModel):
    hasInteraction: bool
    count: int
    results: List[InteractionResult]
    ingredientCodeCheckAvailable: bool = False
    message: str


# =========================
# 중복복용 검사
# =========================

class DuplicateCheckRequest(BaseModel):
    itemSeqs: List[str]


class SameDrugDuplicate(BaseModel):
    itemSeq: str
    itemName: str
    count: int
    message: str


class IngredientCodeDuplicate(BaseModel):
    codeType: str = ""
    ingredientCode: str = ""
    ingredient: str = ""
    itemSeqs: List[str]
    items: List[str]
    sources: List[str] = []
    message: str


class AtcDuplicate(BaseModel):
    atcCode: str = ""
    ingredient: str = ""
    itemSeqs: List[str]
    items: List[str]
    message: str


class EffectGroupDuplicate(BaseModel):
    type: str = ""
    effectName: str = ""
    seriesName: str = ""
    itemSeqs: List[str]
    items: List[str]
    ingredients: List[str] = []
    message: str


class IngredientNameDuplicate(BaseModel):
    ingredient: str = ""
    itemSeqs: List[str]
    items: List[str]
    message: str


class DuplicateCheckResponse(BaseModel):
    hasDuplicate: bool
    sameDrug: List[SameDrugDuplicate] = []
    ingredientCodeDuplicate: List[IngredientCodeDuplicate] = []
    atcDuplicate: List[AtcDuplicate] = []
    effectGroupDuplicate: List[EffectGroupDuplicate] = []
    ingredientNameDuplicate: List[IngredientNameDuplicate] = []
