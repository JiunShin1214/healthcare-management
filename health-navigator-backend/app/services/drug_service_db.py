import re
from collections import Counter

from sqlalchemy import or_

from app.models.drug import (
    DrugItem,
    DrugDetail,
    EasyDrug,
    DurInteraction,
    DurDuplicate,
)

from app.models.user_medication import UserMedication


# =========================
# 공통 함수
# =========================

def clean_value(value):
    if value is None:
        return ""
    value = str(value).strip()
    if value.lower() in ["none", "nan", "null"]:
        return ""
    return value


def normalize_text(value):
    text = clean_value(value).lower()
    text = re.sub(r"\s+", "", text)
    text = text.replace("-", "")
    text = text.replace("/", "")
    text = text.replace(",", "")
    return text


def extract_mfds_ingredients(main_item_ingr):
    text = clean_value(main_item_ingr)
    if not text:
        return []

    pattern = r"\[([^\]]+)\]([^/\|]+)"
    matches = re.findall(pattern, text)

    return [
        {
            "ingredient_code": clean_value(code),
            "ingredient_name": clean_value(name),
            "source": "drug_details",
        }
        for code, name in matches
    ]


# =========================
# 1. 기본 약 목록
# =========================

def get_drug_list(db, limit: int = 20):
    rows = (
        db.query(DrugItem)
        .filter(DrugItem.cancel_name == "정상")
        .order_by(DrugItem.item_name.asc(), DrugItem.item_seq.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "itemSeq": clean_value(row.item_seq),
            "itemName": clean_value(row.item_name),
            "entpName": clean_value(row.entp_name),
            "ingredientName": clean_value(row.ingredient_name),
            "ingredientCount": clean_value(row.ingredient_count),
            "productType": clean_value(row.product_type),
            "etcOtc": clean_value(row.etc_otc),
            "imageUrl": clean_value(row.image_url),
        }
        for row in rows
    ]


# =========================
# 2. 약 검색
# =========================

def search_drugs(db, q: str):
    q = q.strip()

    if not q:
        return []

    rows = (
        db.query(DrugItem)
        .filter(DrugItem.cancel_name == "정상")
        .filter(
            or_(
                DrugItem.item_name.like(f"%{q}%"),
                DrugItem.item_seq.like(f"%{q}%"),
            )
        )
        .order_by(DrugItem.item_name.asc(), DrugItem.item_seq.asc())
        .limit(30)
        .all()
    )

    return [
        {
            "itemSeq": clean_value(row.item_seq),
            "itemName": clean_value(row.item_name),
            "entpName": clean_value(row.entp_name),
            "ingredientName": clean_value(row.ingredient_name),
            "ingredientCount": clean_value(row.ingredient_count),
            "productType": clean_value(row.product_type),
            "etcOtc": clean_value(row.etc_otc),
            "imageUrl": clean_value(row.image_url),
        }
        for row in rows
    ]


def autocomplete_drugs(db, q: str, limit: int = 10):
    q = q.strip()
    limit = max(1, min(limit, 20))

    if not q:
        return []

    rows = (
        db.query(DrugItem)
        .filter(DrugItem.cancel_name == "정상")
        .filter(
            or_(
                DrugItem.item_name.like(f"%{q}%"),
                DrugItem.item_seq.like(f"%{q}%"),
            )
        )
        .order_by(
            DrugItem.item_name.like(f"{q}%").desc(),
            DrugItem.item_name.asc(),
            DrugItem.item_seq.asc(),
        )
        .limit(limit)
        .all()
    )

    return [
        {
            "itemSeq": clean_value(row.item_seq),
            "itemName": clean_value(row.item_name),
            "entpName": clean_value(row.entp_name),
        }
        for row in rows
    ]


# =========================
# 3. 약 상세 조회
# =========================

def get_drug_detail(db, item_seq: str):
    item_seq = str(item_seq)

    basic = (
        db.query(DrugItem)
        .filter(DrugItem.item_seq == item_seq)
        .first()
    )

    detail = (
        db.query(DrugDetail)
        .filter(DrugDetail.item_seq == item_seq)
        .first()
    )

    easy = (
        db.query(EasyDrug)
        .filter(EasyDrug.item_seq == item_seq)
        .first()
    )

    if basic is None and detail is None and easy is None:
        return None

    response = {
        "itemSeq": item_seq,
        "itemName": "",
        "itemEngName": "",
        "entpName": "",
        "ingredient": "",
        "productType": "",
        "etcOtc": "",
        "imageUrl": "",

        "chart": "",
        "storage": "",

        "effect": "",
        "useMethod": "",
        "warning": "",
        "sideEffect": "",

        "ediCode": "",
        "atcCode": "",
        "packUnit": "",
        "cancelName": "",
        "permitDate": "",

        "hasMedicationInfo": False,
        "missingInfoFields": [],
    }

    if basic is not None:
        response["itemName"] = clean_value(basic.item_name)
        response["itemEngName"] = clean_value(basic.item_eng_name)
        response["entpName"] = clean_value(basic.entp_name)
        response["ingredient"] = clean_value(basic.ingredient_name)
        response["productType"] = clean_value(basic.product_type)
        response["etcOtc"] = clean_value(basic.etc_otc)
        response["imageUrl"] = clean_value(basic.image_url)
        response["ediCode"] = clean_value(basic.edi_code)
        response["cancelName"] = clean_value(basic.cancel_name)
        response["permitDate"] = clean_value(basic.permit_date)

    if detail is not None:
        response["itemName"] = response["itemName"] or clean_value(detail.item_name)
        response["itemEngName"] = response["itemEngName"] or clean_value(detail.item_eng_name)
        response["entpName"] = response["entpName"] or clean_value(detail.entp_name)
        response["etcOtc"] = response["etcOtc"] or clean_value(detail.etc_otc_code)
        response["ingredient"] = response["ingredient"] or clean_value(detail.main_item_ingr)

        response["effect"] = clean_value(detail.ee_doc_data)
        response["useMethod"] = clean_value(detail.ud_doc_data)
        response["warning"] = clean_value(detail.nb_doc_data)
        response["storage"] = clean_value(detail.storage_method)
        response["chart"] = clean_value(detail.chart)
        response["atcCode"] = clean_value(detail.atc_code)
        response["packUnit"] = clean_value(detail.pack_unit)

        response["ediCode"] = response["ediCode"] or clean_value(detail.edi_code)
        response["cancelName"] = response["cancelName"] or clean_value(detail.cancel_name)
        response["permitDate"] = response["permitDate"] or clean_value(detail.permit_date)

    if easy is not None:
        response["itemName"] = clean_value(easy.item_name) or response["itemName"]
        response["entpName"] = clean_value(easy.entp_name) or response["entpName"]
        response["effect"] = clean_value(easy.effect) or response["effect"]
        response["useMethod"] = clean_value(easy.use_method) or response["useMethod"]
        response["warning"] = clean_value(easy.caution) or clean_value(easy.warning) or response["warning"]
        response["sideEffect"] = clean_value(easy.side_effect) or response["sideEffect"]
        response["storage"] = clean_value(easy.deposit_method) or response["storage"]
        response["imageUrl"] = clean_value(easy.image_url) or response["imageUrl"]

    required_info = {
        "effect": "효능",
        "useMethod": "복용법",
        "warning": "주의사항",
        "sideEffect": "부작용",
    }

    response["missingInfoFields"] = [
        label for key, label in required_info.items()
        if not response.get(key)
    ]

    response["hasMedicationInfo"] = len(response["missingInfoFields"]) < len(required_info)

    return response

# =========================
# 4. 병용금기 검사 DB 버전
# =========================

def check_interaction(db, current_item_seqs: list[str], new_item_seq: str):
    current_item_seqs = list(dict.fromkeys(map(str, current_item_seqs)))
    new_item_seq = str(new_item_seq)

    results = []
    seen = set()

    def add_result(
        source,
        type_name,
        drug_a_seq,
        drug_a_name,
        ingredient_a,
        drug_b_seq,
        drug_b_name,
        ingredient_b,
        reason,
    ):
        drug_pair_key = "|".join(sorted([
            clean_value(drug_a_seq),
            clean_value(drug_b_seq)
        ]))

        ingredient_pair_key = "|".join(sorted([
            clean_value(ingredient_a),
            clean_value(ingredient_b)
        ]))

        dedup_key = (
            drug_pair_key,
            ingredient_pair_key,
            clean_value(type_name),
            clean_value(reason)
        )

        if dedup_key in seen:
            return

        seen.add(dedup_key)

        results.append({
            "source": source,
            "type": clean_value(type_name) or "병용금기",
            "drugASeq": clean_value(drug_a_seq),
            "drugAName": clean_value(drug_a_name),
            "ingredientA": clean_value(ingredient_a),
            "drugBSeq": clean_value(drug_b_seq),
            "drugBName": clean_value(drug_b_name),
            "ingredientB": clean_value(ingredient_b),
            "reason": clean_value(reason) or "사유 정보 없음"
        })

    # =========================
    # 1. 제품코드 기준
    # =========================

    direct_rows = (
        db.query(DurInteraction)
        .filter(
            or_(
                (
                    DurInteraction.item_seq.in_(current_item_seqs)
                    & (DurInteraction.mixture_item_seq == new_item_seq)
                ),
                (
                    DurInteraction.mixture_item_seq.in_(current_item_seqs)
                    & (DurInteraction.item_seq == new_item_seq)
                )
            )
        )
        .all()
    )

    direct_seen = set()

    for row in direct_rows:
        direct_key = (
            clean_value(row.item_seq),
            clean_value(row.mixture_item_seq),
            clean_value(row.type_name),
            clean_value(row.prohibt_content),
        )

        if direct_key in direct_seen:
            continue

        direct_seen.add(direct_key)

        add_result(
            source="제품코드 기준",
            type_name=row.type_name,
            drug_a_seq=row.item_seq,
            drug_a_name=row.item_name,
            ingredient_a=row.ingr_name,
            drug_b_seq=row.mixture_item_seq,
            drug_b_name=row.mixture_item_name,
            ingredient_b=row.mixture_ingr_name,
            reason=row.prohibt_content
        )

    # =========================
    # 2. 성분코드 기준
    # =========================

    selected_ingredients = get_selected_ingredients(
        db=db,
        item_seqs=current_item_seqs + [new_item_seq]
    )

    current_ingredients = [
        row for row in selected_ingredients
        if row["itemSeq"] in current_item_seqs
        and row["codeType"] == "DUR_INGR"
        and row["ingredientCode"] != ""
    ]

    new_ingredients = [
        row for row in selected_ingredients
        if row["itemSeq"] == new_item_seq
        and row["codeType"] == "DUR_INGR"
        and row["ingredientCode"] != ""
    ]

    current_codes = {row["ingredientCode"] for row in current_ingredients}
    new_codes = {row["ingredientCode"] for row in new_ingredients}

    if current_codes and new_codes:
        ingredient_rows = (
            db.query(DurInteraction)
            .filter(
                or_(
                    (
                        DurInteraction.ingr_code.in_(current_codes)
                        & DurInteraction.mixture_ingr_code.in_(new_codes)
                    ),
                    (
                        DurInteraction.mixture_ingr_code.in_(current_codes)
                        & DurInteraction.ingr_code.in_(new_codes)
                    )
                )
            )
            .all()
        )

        ingredient_seen = set()

        for row in ingredient_rows:
            ingr_code = clean_value(row.ingr_code)
            mixture_code = clean_value(row.mixture_ingr_code)

            ingredient_key = (
                ingr_code,
                mixture_code,
                clean_value(row.type_name),
                clean_value(row.prohibt_content),
            )

            if ingredient_key in ingredient_seen:
                continue

            ingredient_seen.add(ingredient_key)

            if ingr_code in current_codes and mixture_code in new_codes:
                matched_current = [
                    cur for cur in current_ingredients
                    if cur["ingredientCode"] == ingr_code
                ]

                for cur in matched_current:
                    add_result(
                        source="성분코드 기준",
                        type_name=row.type_name,
                        drug_a_seq=cur["itemSeq"],
                        drug_a_name=get_drug_name(db, cur["itemSeq"]),
                        ingredient_a=row.ingr_name,
                        drug_b_seq=new_item_seq,
                        drug_b_name=get_drug_name(db, new_item_seq),
                        ingredient_b=row.mixture_ingr_name,
                        reason=row.prohibt_content
                    )

            if mixture_code in current_codes and ingr_code in new_codes:
                matched_current = [
                    cur for cur in current_ingredients
                    if cur["ingredientCode"] == mixture_code
                ]

                for cur in matched_current:
                    add_result(
                        source="성분코드 기준",
                        type_name=row.type_name,
                        drug_a_seq=cur["itemSeq"],
                        drug_a_name=get_drug_name(db, cur["itemSeq"]),
                        ingredient_a=row.mixture_ingr_name,
                        drug_b_seq=new_item_seq,
                        drug_b_name=get_drug_name(db, new_item_seq),
                        ingredient_b=row.ingr_name,
                        reason=row.prohibt_content
                    )

    return {
        "hasInteraction": len(results) > 0,
        "count": len(results),
        "results": results,
        "ingredientCodeCheckAvailable": bool(current_codes and new_codes),
        "message": (
            "병용금기 결과가 확인되었습니다."
            if results
            else "현재 보유한 DUR 데이터 기준으로 확인된 병용금기 정보가 없습니다."
        )
    }


# =========================
# 5. 중복복용 검사 DB 버전
# =========================

def check_duplicate(db, item_seqs: list[str]):
    item_seqs = list(map(str, item_seqs))

    counts = Counter(item_seqs)
    same_drug_results = []

    for item_seq, count in counts.items():
        if count >= 2:
            same_drug_results.append({
                "itemSeq": item_seq,
                "itemName": get_drug_name(db, item_seq),
                "count": count,
                "message": "같은 약이 2회 이상 선택되었습니다."
            })

    unique_item_seqs = list(dict.fromkeys(item_seqs))

    selected_ingredients = get_selected_ingredients(
        db=db,
        item_seqs=unique_item_seqs
    )

    # 1. 성분 코드 기준 중복
    ingredient_code_results = []

    code_rows = [
        row for row in selected_ingredients
        if row["ingredientCode"] != ""
    ]

    code_map = {}

    for row in code_rows:
        key = (row["codeType"], row["ingredientCode"])
        code_map.setdefault(key, []).append(row)

    for (code_type, ingredient_code), rows in code_map.items():
        seqs = list(dict.fromkeys([r["itemSeq"] for r in rows]))
        if len(seqs) >= 2:
            ingredient_code_results.append({
                "codeType": clean_value(code_type),
                "ingredientCode": clean_value(ingredient_code),
                "ingredient": clean_value(rows[0]["ingredientName"]),
                "itemSeqs": seqs,
                "items": [get_drug_name(db, seq) for seq in seqs],
                "sources": list(dict.fromkeys([r["source"] for r in rows])),
                "message": "성분 코드 기준으로 같은 성분 의약품이 중복 선택되었습니다."
            })

    # 2. ATC 코드 기준 중복
    atc_results = []

    details = (
        db.query(DrugDetail)
        .filter(DrugDetail.item_seq.in_(unique_item_seqs))
        .all()
    )

    atc_map = {}

    for row in details:
        atc_code = clean_value(row.atc_code)
        if atc_code:
            atc_map.setdefault(atc_code, []).append(row)

    for atc_code, rows in atc_map.items():
        seqs = list(dict.fromkeys([clean_value(r.item_seq) for r in rows]))
        if len(seqs) >= 2:
            atc_results.append({
                "atcCode": atc_code,
                "ingredient": clean_value(rows[0].main_item_ingr),
                "itemSeqs": seqs,
                "items": [get_drug_name(db, seq) for seq in seqs],
                "message": "ATC 코드 기준으로 같은 주성분 또는 같은 계열 의약품이 중복 선택되었습니다."
            })

    # 3. 효능군 중복
    effect_group_results = []

    duplicate_rows = (
        db.query(DurDuplicate)
        .filter(DurDuplicate.item_seq.in_(unique_item_seqs))
        .all()
    )

    effect_map = {}

    for row in duplicate_rows:
        key = (
            clean_value(row.effect_name),
            clean_value(row.sers_name)
        )

        if key == ("", ""):
            continue

        effect_map.setdefault(key, []).append(row)

    for (effect_name, sers_name), rows in effect_map.items():
        seqs = list(dict.fromkeys([clean_value(r.item_seq) for r in rows]))

        if len(seqs) >= 2:
            effect_group_results.append({
                "type": clean_value(rows[0].type_name) or "효능군중복",
                "effectName": effect_name,
                "seriesName": sers_name,
                "itemSeqs": seqs,
                "items": [get_drug_name(db, seq) for seq in seqs],
                "ingredients": list(dict.fromkeys([
                    clean_value(r.ingr_name)
                    for r in rows
                    if clean_value(r.ingr_name)
                ])),
                "message": "같은 효능군 또는 계열의 약이 중복 선택되었습니다."
            })

    # 4. 성분명 기준 중복
    ingredient_name_results = []

    name_rows = [
        row for row in selected_ingredients
        if row["ingredientKey"] != ""
    ]

    name_map = {}

    for row in name_rows:
        key = row["ingredientKey"]
        name_map.setdefault(key, []).append(row)

    for key, rows in name_map.items():
        seqs = list(dict.fromkeys([r["itemSeq"] for r in rows]))

        if len(seqs) >= 2:
            ingredient_name_results.append({
                "ingredient": clean_value(rows[0]["ingredientName"]),
                "itemSeqs": seqs,
                "items": [get_drug_name(db, seq) for seq in seqs],
                "message": "표준화된 성분명 기준으로 같은 성분 의약품이 중복 선택되었습니다."
            })

    return {
        "hasDuplicate": (
            len(same_drug_results) > 0
            or len(ingredient_code_results) > 0
            or len(atc_results) > 0
            or len(effect_group_results) > 0
            or len(ingredient_name_results) > 0
        ),
        "sameDrug": same_drug_results,
        "ingredientCodeDuplicate": ingredient_code_results,
        "atcDuplicate": atc_results,
        "effectGroupDuplicate": effect_group_results,
        "ingredientNameDuplicate": ingredient_name_results
    }


# =========================
# 6. 사용자 복용약 목록 조회
# =========================

def get_user_medications(db, user_id: int):
    medications = (
        db.query(UserMedication)
        .filter(UserMedication.user_id == user_id)
        .order_by(UserMedication.created_at.desc())
        .all()
    )

    return [
        {
            "id": medication.id,
            "itemSeq": medication.item_seq,
            "itemName": medication.item_name,
            "entpName": medication.entp_name or "",
            "memo": medication.memo or "",
            "createdAt": str(medication.created_at)
        }
        for medication in medications
    ]


# =========================
# 7. 사용자 복용약 추가
# =========================

def add_user_medication(db, user_id: int, item_seq: str, memo: str = ""):
    item_seq = str(item_seq)

    existing = (
        db.query(UserMedication)
        .filter(
            UserMedication.user_id == user_id,
            UserMedication.item_seq == item_seq
        )
        .first()
    )

    if existing is not None:
        return "DUPLICATED"

    detail = get_drug_detail(db=db, item_seq=item_seq)

    if detail is None:
        return None

    medication = UserMedication(
        user_id=user_id,
        item_seq=item_seq,
        item_name=detail.get("itemName", ""),
        entp_name=detail.get("entpName", ""),
        memo=memo or ""
    )

    db.add(medication)
    db.commit()
    db.refresh(medication)

    return {
        "id": medication.id,
        "itemSeq": medication.item_seq,
        "itemName": medication.item_name,
        "entpName": medication.entp_name or "",
        "memo": medication.memo or "",
        "createdAt": str(medication.created_at)
    }


# =========================
# 8. 사용자 복용약 삭제
# =========================

def delete_user_medication(db, user_id: int, medication_id: int):
    medication = (
        db.query(UserMedication)
        .filter(
            UserMedication.id == medication_id,
            UserMedication.user_id == user_id
        )
        .first()
    )

    if medication is None:
        return False

    db.delete(medication)
    db.commit()

    return True


# =========================
# 9. 내 복용약 기준 병용금기 검사
# =========================

def check_my_interaction(db, user_id: int, new_item_seqs: list[str]):
    medications = (
        db.query(UserMedication)
        .filter(UserMedication.user_id == user_id)
        .all()
    )

    current_item_seqs = [str(m.item_seq) for m in medications]
    new_item_seqs = list(dict.fromkeys(map(str, new_item_seqs)))

    if not current_item_seqs or not new_item_seqs:
        return {
            "hasInteraction": False,
            "count": 0,
            "results": [],
            "ingredientCodeCheckAvailable": False,
            "message": "검사할 복용약 또는 새 약이 없습니다."
        }

    results = []
    seen = set()
    ingredient_available = False

    for new_item_seq in new_item_seqs:
        result = check_interaction(
            db=db,
            current_item_seqs=current_item_seqs,
            new_item_seq=new_item_seq
        )

        if result.get("ingredientCodeCheckAvailable"):
            ingredient_available = True

        for item in result.get("results", []):
            key = (
                item.get("source", ""),
                item.get("drugASeq", ""),
                item.get("drugBSeq", ""),
                item.get("ingredientA", ""),
                item.get("ingredientB", ""),
                item.get("reason", "")
            )

            if key in seen:
                continue

            seen.add(key)
            results.append(item)

    return {
        "hasInteraction": len(results) > 0,
        "count": len(results),
        "results": results,
        "ingredientCodeCheckAvailable": ingredient_available,
        "message": (
            "병용금기 결과가 확인되었습니다."
            if results
            else "현재 보유한 DUR 데이터 기준으로 확인된 병용금기 정보가 없습니다."
        )
    }
# =========================
# 10. 내 복용약 기준 중복복용 검사
# =========================

def check_my_duplicate(db, user_id: int, include_new_item_seqs: list[str] | None = None):
    medications = (
        db.query(UserMedication)
        .filter(UserMedication.user_id == user_id)
        .all()
    )

    item_seqs = [m.item_seq for m in medications]

    if include_new_item_seqs:
        item_seqs.extend(map(str, include_new_item_seqs))

    return check_duplicate(
        db=db,
        item_seqs=item_seqs
    )

def get_drug_name(db, item_seq: str):
    item_seq = str(item_seq)

    drug = (
        db.query(DrugItem)
        .filter(DrugItem.item_seq == item_seq)
        .first()
    )

    if drug:
        return clean_value(drug.item_name)

    detail = (
        db.query(DrugDetail)
        .filter(DrugDetail.item_seq == item_seq)
        .first()
    )

    if detail:
        return clean_value(detail.item_name)

    return item_seq


def get_selected_ingredients(db, item_seqs: list[str]):
    item_seqs = list(dict.fromkeys(map(str, item_seqs)))
    rows = []

    # 1. DrugDetail MAIN_ITEM_INGR
    details = (
        db.query(DrugDetail)
        .filter(DrugDetail.item_seq.in_(item_seqs))
        .all()
    )

    for detail in details:
        ingredients = extract_mfds_ingredients(detail.main_item_ingr)

        for ing in ingredients:
            rows.append({
                "itemSeq": clean_value(detail.item_seq),
                "itemName": clean_value(detail.item_name),
                "ingredientCode": clean_value(ing["ingredient_code"]),
                "ingredientName": clean_value(ing["ingredient_name"]),
                "codeType": "MFDS_MAIN_INGR",
                "atcCode": clean_value(detail.atc_code),
                "source": "drug_details",
                "ingredientKey": normalize_text(ing["ingredient_name"]),
            })

        if not ingredients and detail.main_ingr_eng:
            rows.append({
                "itemSeq": clean_value(detail.item_seq),
                "itemName": clean_value(detail.item_name),
                "ingredientCode": "",
                "ingredientName": clean_value(detail.main_ingr_eng),
                "codeType": "NAME_ONLY",
                "atcCode": clean_value(detail.atc_code),
                "source": "drug_details",
                "ingredientKey": normalize_text(detail.main_ingr_eng),
            })

    # 2. DurDuplicate
    duplicates = (
        db.query(DurDuplicate)
        .filter(DurDuplicate.item_seq.in_(item_seqs))
        .all()
    )

    for row in duplicates:
        rows.append({
            "itemSeq": clean_value(row.item_seq),
            "itemName": clean_value(row.item_name),
            "ingredientCode": clean_value(row.ingr_code),
            "ingredientName": clean_value(row.ingr_name),
            "codeType": "DUR_INGR",
            "atcCode": "",
            "source": "dur_duplicates",
            "ingredientKey": normalize_text(row.ingr_name),
        })

    # 3. DurInteraction - ITEM_SEQ 쪽
    interactions_a = (
        db.query(DurInteraction)
        .filter(DurInteraction.item_seq.in_(item_seqs))
        .all()
    )

    for row in interactions_a:
        rows.append({
            "itemSeq": clean_value(row.item_seq),
            "itemName": clean_value(row.item_name),
            "ingredientCode": clean_value(row.ingr_code),
            "ingredientName": clean_value(row.ingr_name),
            "codeType": "DUR_INGR",
            "atcCode": "",
            "source": "dur_interactions",
            "ingredientKey": normalize_text(row.ingr_name),
        })

    # 4. DurInteraction - MIXTURE_ITEM_SEQ 쪽
    interactions_b = (
        db.query(DurInteraction)
        .filter(DurInteraction.mixture_item_seq.in_(item_seqs))
        .all()
    )

    for row in interactions_b:
        rows.append({
            "itemSeq": clean_value(row.mixture_item_seq),
            "itemName": clean_value(row.mixture_item_name),
            "ingredientCode": clean_value(row.mixture_ingr_code),
            "ingredientName": clean_value(row.mixture_ingr_name),
            "codeType": "DUR_INGR",
            "atcCode": "",
            "source": "dur_interactions",
            "ingredientKey": normalize_text(row.mixture_ingr_name),
        })

    # 중복 제거
    unique = []
    seen = set()

    for row in rows:
        key = (
            row["itemSeq"],
            row["ingredientCode"],
            row["ingredientName"],
            row["codeType"],
            row["source"],
        )

        if row["itemSeq"] == "":
            continue

        if (
            row["ingredientCode"] == ""
            and row["ingredientName"] == ""
            and row["atcCode"] == ""
        ):
            continue

        if key in seen:
            continue

        seen.add(key)
        unique.append(row)

    return unique
