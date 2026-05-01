import re
import pandas as pd
from pathlib import Path
from collections import Counter
from app.models.user_medication import UserMedication



BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


# =========================
# parquet 로드
# =========================

permit_list = pd.read_parquet(DATA_DIR / "permit_list.parquet")
permit_detail = pd.read_parquet(DATA_DIR / "permit_detail.parquet")
easy_drug = pd.read_parquet(DATA_DIR / "easy_drug.parquet")
dur_taboo = pd.read_parquet(DATA_DIR / "dur_taboo.parquet")
dur_duplicate = pd.read_parquet(DATA_DIR / "dur_duplicate.parquet")


# =========================
# 공통 함수
# =========================

def clean_value(value):
    if pd.isna(value):
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

    results = []
    for code, name in matches:
        results.append({
            "ingredient_code": clean_value(code),
            "ingredient_name": clean_value(name),
            "source": "permit_detail"
        })

    return results


def build_ingredient_index():
    rows = []

    for _, row in permit_detail.iterrows():
        item_seq = clean_value(row.get("ITEM_SEQ"))
        item_name = clean_value(row.get("ITEM_NAME"))

        ingredients = extract_mfds_ingredients(row.get("MAIN_ITEM_INGR"))

        for ing in ingredients:
            rows.append({
                "ITEM_SEQ": item_seq,
                "ITEM_NAME": item_name,
                "INGREDIENT_CODE": ing["ingredient_code"],
                "INGREDIENT_NAME": ing["ingredient_name"],
                "CODE_TYPE": "MFDS_MAIN_INGR",
                "ATC_CODE": clean_value(row.get("ATC_CODE")),
                "SOURCE": "permit_detail"
            })

        if not ingredients:
            main_eng = clean_value(row.get("MAIN_INGR_ENG"))
            if main_eng:
                rows.append({
                    "ITEM_SEQ": item_seq,
                    "ITEM_NAME": item_name,
                    "INGREDIENT_CODE": "",
                    "INGREDIENT_NAME": main_eng,
                    "CODE_TYPE": "NAME_ONLY",
                    "ATC_CODE": clean_value(row.get("ATC_CODE")),
                    "SOURCE": "permit_detail"
                })

    for _, row in dur_duplicate.iterrows():
        rows.append({
            "ITEM_SEQ": clean_value(row.get("ITEM_SEQ")),
            "ITEM_NAME": clean_value(row.get("ITEM_NAME")),
            "INGREDIENT_CODE": clean_value(row.get("INGR_CODE")),
            "INGREDIENT_NAME": clean_value(row.get("INGR_NAME")),
            "CODE_TYPE": "DUR_INGR",
            "ATC_CODE": "",
            "SOURCE": "dur_duplicate"
        })

    for _, row in dur_taboo.iterrows():
        rows.append({
            "ITEM_SEQ": clean_value(row.get("ITEM_SEQ")),
            "ITEM_NAME": clean_value(row.get("ITEM_NAME")),
            "INGREDIENT_CODE": clean_value(row.get("INGR_CODE")),
            "INGREDIENT_NAME": clean_value(row.get("INGR_KOR_NAME")),
            "CODE_TYPE": "DUR_INGR",
            "ATC_CODE": "",
            "SOURCE": "dur_taboo"
        })

        rows.append({
            "ITEM_SEQ": clean_value(row.get("MIXTURE_ITEM_SEQ")),
            "ITEM_NAME": clean_value(row.get("MIXTURE_ITEM_NAME")),
            "INGREDIENT_CODE": clean_value(row.get("MIXTURE_INGR_CODE")),
            "INGREDIENT_NAME": clean_value(row.get("MIXTURE_INGR_KOR_NAME")),
            "CODE_TYPE": "DUR_INGR",
            "ATC_CODE": "",
            "SOURCE": "dur_taboo"
        })

    df = pd.DataFrame(rows)

    if df.empty:
        return df

    df = df[
        (df["ITEM_SEQ"] != "")
        & (
            (df["INGREDIENT_CODE"] != "")
            | (df["INGREDIENT_NAME"] != "")
            | (df["ATC_CODE"] != "")
        )
    ].copy()

    df["INGREDIENT_KEY"] = df["INGREDIENT_NAME"].apply(normalize_text)
    df = df.drop_duplicates()

    return df


# =========================
# 문자열 비교 안정화
# =========================

permit_list["ITEM_SEQ"] = permit_list["ITEM_SEQ"].astype(str)
permit_detail["ITEM_SEQ"] = permit_detail["ITEM_SEQ"].astype(str)
easy_drug["itemSeq"] = easy_drug["itemSeq"].astype(str)
dur_taboo["ITEM_SEQ"] = dur_taboo["ITEM_SEQ"].astype(str)
dur_taboo["MIXTURE_ITEM_SEQ"] = dur_taboo["MIXTURE_ITEM_SEQ"].astype(str)
dur_duplicate["ITEM_SEQ"] = dur_duplicate["ITEM_SEQ"].astype(str)

ingredient_index = build_ingredient_index()






# 기본으로 출력되는 약 리스트 
def get_drug_list(limit: int = 20):
    df = permit_list.copy()

    if "CANCEL_NAME" in df.columns:
        df = df[df["CANCEL_NAME"] == "정상"]

    df["ITEM_NAME_SORT"] = (
        df["ITEM_NAME"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    df = df.sort_values(
        by=["ITEM_NAME_SORT", "ITEM_SEQ"],
        ascending=[True, True],
        kind="mergesort"
    )

    result = df.head(limit)

    rows = result.fillna("").to_dict(orient="records")

    return [
        {
            "itemSeq": clean_value(row.get("ITEM_SEQ")),
            "itemName": clean_value(row.get("ITEM_NAME")),
            "entpName": clean_value(row.get("ENTP_NAME")),
            "ingredientName": clean_value(row.get("ITEM_INGR_NAME")),
            "ingredientCount": clean_value(row.get("ITEM_INGR_CNT")),
            "productType": clean_value(row.get("PRDUCT_TYPE")),
            "etcOtc": clean_value(row.get("SPCLTY_PBLC")),
            "imageUrl": clean_value(row.get("BIG_PRDT_IMG_URL")),
        }
        for row in rows
    ]



# =========================
# 1. 약 검색
# =========================

def search_drugs(q: str):
    if not q.strip():
        return []

    df = permit_list.copy()

    if "CANCEL_NAME" in df.columns:
        df = df[df["CANCEL_NAME"] == "정상"]

    result = df[
        df["ITEM_NAME"].fillna("").str.contains(q, case=False, na=False)
    ].head(30)

    rows = result.fillna("").to_dict(orient="records")

    return [
        {
            "itemSeq": clean_value(row.get("ITEM_SEQ")),
            "itemName": clean_value(row.get("ITEM_NAME")),
            "entpName": clean_value(row.get("ENTP_NAME")),
            "ingredientName": clean_value(row.get("ITEM_INGR_NAME")),
            "ingredientCount": clean_value(row.get("ITEM_INGR_CNT")),
            "productType": clean_value(row.get("PRDUCT_TYPE")),
            "etcOtc": clean_value(row.get("SPCLTY_PBLC")),
            "imageUrl": clean_value(row.get("BIG_PRDT_IMG_URL")),
        }
        for row in rows
    ]


# =========================
# 2. 약 상세 조회
# =========================

def get_drug_detail(item_seq: str):
    item_seq = str(item_seq)

    basic = permit_list[permit_list["ITEM_SEQ"] == item_seq]
    detail = permit_detail[permit_detail["ITEM_SEQ"] == item_seq]
    easy = easy_drug[easy_drug["itemSeq"] == item_seq]

    if basic.empty and detail.empty and easy.empty:
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

    if not basic.empty:
        row = basic.iloc[0]

        response["itemName"] = clean_value(row.get("ITEM_NAME"))
        response["itemEngName"] = clean_value(row.get("ITEM_ENG_NAME"))
        response["entpName"] = clean_value(row.get("ENTP_NAME"))
        response["ingredient"] = clean_value(row.get("ITEM_INGR_NAME"))
        response["productType"] = clean_value(row.get("PRDUCT_TYPE"))
        response["imageUrl"] = clean_value(row.get("BIG_PRDT_IMG_URL"))
        response["ediCode"] = clean_value(row.get("EDI_CODE"))
        response["cancelName"] = clean_value(row.get("CANCEL_NAME"))
        response["permitDate"] = clean_value(row.get("ITEM_PERMIT_DATE"))

    if not detail.empty:
        row = detail.iloc[0]

        response["itemName"] = response["itemName"] or clean_value(row.get("ITEM_NAME"))
        response["itemEngName"] = response["itemEngName"] or clean_value(row.get("ITEM_ENG_NAME"))
        response["entpName"] = response["entpName"] or clean_value(row.get("ENTP_NAME"))
        response["etcOtc"] = clean_value(row.get("ETC_OTC_CODE"))
        response["ingredient"] = response["ingredient"] or clean_value(row.get("MAIN_ITEM_INGR"))

        response["effect"] = clean_value(row.get("EE_DOC_DATA"))
        response["useMethod"] = clean_value(row.get("UD_DOC_DATA"))
        response["warning"] = clean_value(row.get("NB_DOC_DATA"))
        response["storage"] = clean_value(row.get("STORAGE_METHOD"))
        response["chart"] = clean_value(row.get("CHART"))
        response["atcCode"] = clean_value(row.get("ATC_CODE"))
        response["packUnit"] = clean_value(row.get("PACK_UNIT"))

        response["ediCode"] = response["ediCode"] or clean_value(row.get("EDI_CODE"))
        response["cancelName"] = response["cancelName"] or clean_value(row.get("CANCEL_NAME"))

    if not easy.empty:
        row = easy.iloc[0]

        response["itemName"] = clean_value(row.get("itemName")) or response["itemName"]
        response["entpName"] = clean_value(row.get("entpName")) or response["entpName"]
        response["effect"] = clean_value(row.get("efcyQesitm")) or response["effect"]
        response["useMethod"] = clean_value(row.get("useMethodQesitm")) or response["useMethod"]
        response["warning"] = clean_value(row.get("atpnQesitm")) or response["warning"]
        response["sideEffect"] = clean_value(row.get("seQesitm")) or response["sideEffect"]
        response["storage"] = clean_value(row.get("depositMethodQesitm")) or response["storage"]
        response["imageUrl"] = clean_value(row.get("itemImage")) or response["imageUrl"]

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
# 3. 병용금기 검사
# =========================

def check_interaction(current_item_seqs: list[str], new_item_seq: str):
    current_item_seqs = list(dict.fromkeys(map(str, current_item_seqs)))
    new_item_seq = str(new_item_seq)

    results = []
    seen = set()

    def get_item_name(item_seq: str):
        row = permit_list[permit_list["ITEM_SEQ"] == item_seq]
        if not row.empty:
            return clean_value(row.iloc[0].get("ITEM_NAME"))

        row = permit_detail[permit_detail["ITEM_SEQ"] == item_seq]
        if not row.empty:
            return clean_value(row.iloc[0].get("ITEM_NAME"))

        return item_seq

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

    direct_result = dur_taboo[
        (
            dur_taboo["ITEM_SEQ"].isin(current_item_seqs)
            & (dur_taboo["MIXTURE_ITEM_SEQ"] == new_item_seq)
        )
        |
        (
            dur_taboo["MIXTURE_ITEM_SEQ"].isin(current_item_seqs)
            & (dur_taboo["ITEM_SEQ"] == new_item_seq)
        )
    ].copy()

    direct_result = direct_result.drop_duplicates(
        subset=[
            "ITEM_SEQ",
            "MIXTURE_ITEM_SEQ",
            "TYPE_NAME",
            "PROHBT_CONTENT"
        ]
    )

    for _, row in direct_result.iterrows():
        add_result(
            source="제품코드 기준",
            type_name=row.get("TYPE_NAME"),
            drug_a_seq=row.get("ITEM_SEQ"),
            drug_a_name=row.get("ITEM_NAME"),
            ingredient_a=row.get("INGR_KOR_NAME"),
            drug_b_seq=row.get("MIXTURE_ITEM_SEQ"),
            drug_b_name=row.get("MIXTURE_ITEM_NAME"),
            ingredient_b=row.get("MIXTURE_INGR_KOR_NAME"),
            reason=row.get("PROHBT_CONTENT")
        )

    selected_ingredients = ingredient_index[
        ingredient_index["ITEM_SEQ"].isin(current_item_seqs + [new_item_seq])
    ].copy()

    current_codes = set()
    new_codes = set()

    if not selected_ingredients.empty:
        dur_ingredients = selected_ingredients[
            selected_ingredients["CODE_TYPE"] == "DUR_INGR"
        ].copy()

        current_ingredients = dur_ingredients[
            dur_ingredients["ITEM_SEQ"].isin(current_item_seqs)
        ]

        new_ingredients = dur_ingredients[
            dur_ingredients["ITEM_SEQ"] == new_item_seq
        ]

        current_codes = set(
            current_ingredients["INGREDIENT_CODE"]
            .dropna()
            .astype(str)
            .loc[lambda s: s != ""]
        )

        new_codes = set(
            new_ingredients["INGREDIENT_CODE"]
            .dropna()
            .astype(str)
            .loc[lambda s: s != ""]
        )

        if current_codes and new_codes:
            ingredient_result = dur_taboo[
                (
                    dur_taboo["INGR_CODE"].isin(current_codes)
                    & dur_taboo["MIXTURE_INGR_CODE"].isin(new_codes)
                )
                |
                (
                    dur_taboo["MIXTURE_INGR_CODE"].isin(current_codes)
                    & dur_taboo["INGR_CODE"].isin(new_codes)
                )
            ].copy()

            ingredient_result = ingredient_result.drop_duplicates(
                subset=[
                    "INGR_CODE",
                    "MIXTURE_INGR_CODE",
                    "TYPE_NAME",
                    "PROHBT_CONTENT"
                ]
            )

            for _, row in ingredient_result.iterrows():
                ingr_code = clean_value(row.get("INGR_CODE"))
                mixture_code = clean_value(row.get("MIXTURE_INGR_CODE"))

                if ingr_code in current_codes and mixture_code in new_codes:
                    matched_current = (
                        current_ingredients[
                            current_ingredients["INGREDIENT_CODE"] == ingr_code
                        ]
                        .drop_duplicates(subset=["ITEM_SEQ"])
                    )

                    for _, cur in matched_current.iterrows():
                        add_result(
                            source="성분코드 기준",
                            type_name=row.get("TYPE_NAME"),
                            drug_a_seq=cur.get("ITEM_SEQ"),
                            drug_a_name=get_item_name(clean_value(cur.get("ITEM_SEQ"))),
                            ingredient_a=row.get("INGR_KOR_NAME"),
                            drug_b_seq=new_item_seq,
                            drug_b_name=get_item_name(new_item_seq),
                            ingredient_b=row.get("MIXTURE_INGR_KOR_NAME"),
                            reason=row.get("PROHBT_CONTENT")
                        )

                if mixture_code in current_codes and ingr_code in new_codes:
                    matched_current = (
                        current_ingredients[
                            current_ingredients["INGREDIENT_CODE"] == mixture_code
                        ]
                        .drop_duplicates(subset=["ITEM_SEQ"])
                    )

                    for _, cur in matched_current.iterrows():
                        add_result(
                            source="성분코드 기준",
                            type_name=row.get("TYPE_NAME"),
                            drug_a_seq=cur.get("ITEM_SEQ"),
                            drug_a_name=get_item_name(clean_value(cur.get("ITEM_SEQ"))),
                            ingredient_a=row.get("MIXTURE_INGR_KOR_NAME"),
                            drug_b_seq=new_item_seq,
                            drug_b_name=get_item_name(new_item_seq),
                            ingredient_b=row.get("INGR_KOR_NAME"),
                            reason=row.get("PROHBT_CONTENT")
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
# 4. 중복복용 검사
# =========================

def check_duplicate(item_seqs: list[str]):
    item_seqs = list(map(str, item_seqs))

    counts = Counter(item_seqs)
    same_drug_results = []

    for item_seq, count in counts.items():
        if count >= 2:
            row = permit_list[permit_list["ITEM_SEQ"] == item_seq]
            item_name = item_seq

            if not row.empty:
                item_name = clean_value(row.iloc[0].get("ITEM_NAME"))

            same_drug_results.append({
                "itemSeq": item_seq,
                "itemName": item_name,
                "count": count,
                "message": "같은 약이 2회 이상 선택되었습니다."
            })

    selected_ingredients = ingredient_index[
        ingredient_index["ITEM_SEQ"].isin(item_seqs)
    ].copy()

    ingredient_code_results = []

    if not selected_ingredients.empty:
        code_df = selected_ingredients[
            selected_ingredients["INGREDIENT_CODE"] != ""
        ].copy()

        grouped_code = (
            code_df
            .groupby(["CODE_TYPE", "INGREDIENT_CODE"])
            .agg({
                "ITEM_SEQ": lambda x: list(dict.fromkeys(x)),
                "ITEM_NAME": lambda x: list(dict.fromkeys(x)),
                "INGREDIENT_NAME": "first",
                "SOURCE": lambda x: list(dict.fromkeys(x)),
            })
            .reset_index()
        )

        grouped_code["count"] = grouped_code["ITEM_SEQ"].apply(len)
        duplicated_code = grouped_code[grouped_code["count"] >= 2]

        for _, row in duplicated_code.iterrows():
            ingredient_code_results.append({
                "codeType": clean_value(row.get("CODE_TYPE")),
                "ingredientCode": clean_value(row.get("INGREDIENT_CODE")),
                "ingredient": clean_value(row.get("INGREDIENT_NAME")),
                "itemSeqs": row["ITEM_SEQ"],
                "items": row["ITEM_NAME"],
                "sources": row["SOURCE"],
                "message": "성분 코드 기준으로 같은 성분 의약품이 중복 선택되었습니다."
            })

    atc_results = []

    selected_detail = permit_detail[
        permit_detail["ITEM_SEQ"].isin(item_seqs)
    ].copy()

    if not selected_detail.empty:
        selected_detail["ATC_CODE_CLEAN"] = selected_detail["ATC_CODE"].apply(clean_value)

        atc_grouped = (
            selected_detail[selected_detail["ATC_CODE_CLEAN"] != ""]
            .groupby("ATC_CODE_CLEAN")
            .agg({
                "ITEM_SEQ": lambda x: list(dict.fromkeys(x)),
                "ITEM_NAME": lambda x: list(dict.fromkeys(x)),
                "MAIN_ITEM_INGR": "first",
            })
            .reset_index()
        )

        atc_grouped["count"] = atc_grouped["ITEM_SEQ"].apply(len)
        duplicated_atc = atc_grouped[atc_grouped["count"] >= 2]

        for _, row in duplicated_atc.iterrows():
            atc_results.append({
                "atcCode": clean_value(row.get("ATC_CODE_CLEAN")),
                "ingredient": clean_value(row.get("MAIN_ITEM_INGR")),
                "itemSeqs": row["ITEM_SEQ"],
                "items": row["ITEM_NAME"],
                "message": "ATC 코드 기준으로 같은 주성분 또는 같은 계열 의약품이 중복 선택되었습니다."
            })

    effect_group_results = []

    df = dur_duplicate[dur_duplicate["ITEM_SEQ"].isin(item_seqs)].copy()

    if not df.empty:
        grouped = (
            df.groupby(["EFFECT_NAME", "SERS_NAME"])
            .agg({
                "ITEM_SEQ": lambda x: list(dict.fromkeys(x)),
                "ITEM_NAME": lambda x: list(dict.fromkeys(x)),
                "INGR_NAME": lambda x: list(dict.fromkeys(x)),
                "TYPE_NAME": "first",
            })
            .reset_index()
        )

        grouped["count"] = grouped["ITEM_SEQ"].apply(len)
        duplicated = grouped[grouped["count"] >= 2]

        for _, row in duplicated.iterrows():
            effect_group_results.append({
                "type": clean_value(row.get("TYPE_NAME")) or "효능군중복",
                "effectName": clean_value(row.get("EFFECT_NAME")),
                "seriesName": clean_value(row.get("SERS_NAME")),
                "itemSeqs": row["ITEM_SEQ"],
                "items": row["ITEM_NAME"],
                "ingredients": row["INGR_NAME"],
                "message": "같은 효능군 또는 계열의 약이 중복 선택되었습니다."
            })

    name_results = []

    if not selected_ingredients.empty:
        name_df = selected_ingredients[
            selected_ingredients["INGREDIENT_KEY"] != ""
        ].copy()

        grouped_name = (
            name_df.groupby("INGREDIENT_KEY")
            .agg({
                "ITEM_SEQ": lambda x: list(dict.fromkeys(x)),
                "ITEM_NAME": lambda x: list(dict.fromkeys(x)),
                "INGREDIENT_NAME": "first",
            })
            .reset_index()
        )

        grouped_name["count"] = grouped_name["ITEM_SEQ"].apply(len)
        duplicated_name = grouped_name[grouped_name["count"] >= 2]

        for _, row in duplicated_name.iterrows():
            name_results.append({
                "ingredient": clean_value(row.get("INGREDIENT_NAME")),
                "itemSeqs": row["ITEM_SEQ"],
                "items": row["ITEM_NAME"],
                "message": "표준화된 성분명 기준으로 같은 성분 의약품이 중복 선택되었습니다."
            })

    return {
        "hasDuplicate": (
            len(same_drug_results) > 0
            or len(ingredient_code_results) > 0
            or len(atc_results) > 0
            or len(effect_group_results) > 0
            or len(name_results) > 0
        ),
        "sameDrug": same_drug_results,
        "ingredientCodeDuplicate": ingredient_code_results,
        "atcDuplicate": atc_results,
        "effectGroupDuplicate": effect_group_results,
        "ingredientNameDuplicate": name_results
    }




# =========================
# 5. 사용자 복용약 추가
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

    detail = get_drug_detail(item_seq)

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
# 7. 사용자 복용약 삭제
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
# 8. 내 복용약 + 새 약 병용금기 검사
# =========================

def check_my_interaction(db, user_id: int, new_item_seqs: list[str]):
    medications = (
        db.query(UserMedication)
        .filter(UserMedication.user_id == user_id)
        .all()
    )

    current_item_seqs = [m.item_seq for m in medications]

    results = []
    seen = set()

    for new_item_seq in new_item_seqs:
        result = check_interaction(
            current_item_seqs=current_item_seqs,
            new_item_seq=new_item_seq
        )

        for item in result.get("results", []):
            key = (
                item.get("drugASeq", ""),
                item.get("drugBSeq", ""),
                item.get("ingredientA", ""),
                item.get("ingredientB", ""),
                item.get("reason", "")
            )

            if key not in seen:
                seen.add(key)
                results.append(item)

    return {
        "hasInteraction": len(results) > 0,
        "count": len(results),
        "results": results,
        "ingredientCodeCheckAvailable": True if results else False,
        "message": (
            "병용금기 결과가 확인되었습니다."
            if results
            else "현재 보유한 DUR 데이터 기준으로 확인된 병용금기 정보가 없습니다."
        )
    }


# =========================
# 9. 내 복용약 중복검사
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

    return check_duplicate(item_seqs=item_seqs)