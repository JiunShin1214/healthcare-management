import pandas as pd
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.drug import (
    DrugItem,
    DrugDetail,
    EasyDrug,
    DurInteraction,
    DurDuplicate,
)


db: Session = SessionLocal()


def insert_bulk(model, data):
    objects = [model(**row) for row in data]
    db.bulk_save_objects(objects)
    db.commit()


def import_drug_items():
    df = pd.read_parquet("app/data/permit_list.parquet")

    df = df.fillna("")

    data = [
        {
            "item_seq": str(row["ITEM_SEQ"]),
            "item_name": row["ITEM_NAME"],
            "entp_name": row["ENTP_NAME"],
            "item_eng_name": row.get("ITEM_ENG_NAME", ""),
            "entp_eng_name": row.get("ENTP_ENG_NAME", ""),
            "ingredient_name": row.get("ITEM_INGR_NAME", ""),
            "ingredient_count": str(row.get("ITEM_INGR_CNT", "")),
            "product_type": row.get("PRDUCT_TYPE", ""),
            "etc_otc": row.get("SPCLTY_PBLC", ""),
            "image_url": row.get("BIG_PRDT_IMG_URL", ""),
            "cancel_name": row.get("CANCEL_NAME", ""),
            "permit_date": str(row.get("ITEM_PERMIT_DATE", "")),
            "edi_code": row.get("EDI_CODE", ""),
        }
        for _, row in df.iterrows()
    ]

    insert_bulk(DrugItem, data)


def import_drug_details():
    df = pd.read_parquet("app/data/permit_detail.parquet")
    df = df.fillna("")

    data = [
        {
            "item_seq": str(row["ITEM_SEQ"]),
            "item_name": row.get("ITEM_NAME", ""),
            "entp_name": row.get("ENTP_NAME", ""),
            "item_eng_name": row.get("ITEM_ENG_NAME", ""),
            "entp_eng_name": row.get("ENTP_ENG_NAME", ""),
            "main_item_ingr": row.get("MAIN_ITEM_INGR", ""),
            "main_ingr_eng": row.get("MAIN_INGR_ENG", ""),
            "chart": row.get("CHART", ""),
            "storage_method": row.get("STORAGE_METHOD", ""),
            "valid_term": row.get("VALID_TERM", ""),
            "pack_unit": row.get("PACK_UNIT", ""),
            "ee_doc_data": row.get("EE_DOC_DATA", ""),
            "ud_doc_data": row.get("UD_DOC_DATA", ""),
            "nb_doc_data": row.get("NB_DOC_DATA", ""),
            "atc_code": row.get("ATC_CODE", ""),
            "edi_code": row.get("EDI_CODE", ""),
            "etc_otc_code": row.get("ETC_OTC_CODE", ""),
            "cancel_name": row.get("CANCEL_NAME", ""),
            "permit_date": str(row.get("ITEM_PERMIT_DATE", "")),
        }
        for _, row in df.iterrows()
    ]

    insert_bulk(DrugDetail, data)


def import_easy_drug():
    df = pd.read_parquet("app/data/easy_drug.parquet")
    df = df.fillna("")

    df = df.sort_values(by="updateDe", ascending=False)
    df = df.drop_duplicates(subset=["itemSeq"], keep="first")

    
    data = [
        {
            "item_seq": str(row["itemSeq"]),
            "item_name": row.get("itemName", ""),
            "entp_name": row.get("entpName", ""),
            "effect": row.get("efcyQesitm", ""),
            "use_method": row.get("useMethodQesitm", ""),
            "warning": row.get("atpnWarnQesitm", ""),
            "caution": row.get("atpnQesitm", ""),
            "side_effect": row.get("seQesitm", ""),
            "interaction": row.get("intrcQesitm", ""),
            "deposit_method": row.get("depositMethodQesitm", ""),
            "image_url": row.get("itemImage", ""),
            "open_date": str(row.get("openDe", "")),
            "update_date": str(row.get("updateDe", "")),
        }
        for _, row in df.iterrows()
    ]

    insert_bulk(EasyDrug, data)


def import_dur_interactions():
    df = pd.read_parquet("app/data/dur_taboo.parquet")
    df = df.fillna("")

    data = [
        {
            "dur_seq": row.get("DUR_SEQ", ""),
            "type_name": row.get("TYPE_NAME", ""),
            "item_seq": str(row.get("ITEM_SEQ", "")),
            "item_name": row.get("ITEM_NAME", ""),
            "entp_name": row.get("ENTP_NAME", ""),
            "ingr_code": row.get("INGR_CODE", ""),
            "ingr_name": row.get("INGR_KOR_NAME", ""),
            "mixture_item_seq": str(row.get("MIXTURE_ITEM_SEQ", "")),
            "mixture_item_name": row.get("MIXTURE_ITEM_NAME", ""),
            "mixture_entp_name": row.get("MIXTURE_ENTP_NAME", ""),
            "mixture_ingr_code": row.get("MIXTURE_INGR_CODE", ""),
            "mixture_ingr_name": row.get("MIXTURE_INGR_KOR_NAME", ""),
            "prohibt_content": row.get("PROHBT_CONTENT", ""),
            "remark": row.get("REMARK", ""),
            "notification_date": str(row.get("NOTIFICATION_DATE", "")),
        }
        for _, row in df.iterrows()
    ]

    insert_bulk(DurInteraction, data)


def import_dur_duplicates():
    df = pd.read_parquet("app/data/dur_duplicate.parquet")
    df = df.fillna("")

    data = [
        {
            "dur_seq": row.get("DUR_SEQ", ""),
            "type_name": row.get("TYPE_NAME", ""),
            "item_seq": str(row.get("ITEM_SEQ", "")),
            "item_name": row.get("ITEM_NAME", ""),
            "entp_name": row.get("ENTP_NAME", ""),
            "ingr_code": row.get("INGR_CODE", ""),
            "ingr_name": row.get("INGR_NAME", ""),
            "ingr_eng_name": row.get("INGR_ENG_NAME_FULL", ""),
            "effect_name": row.get("EFFECT_NAME", ""),
            "sers_name": row.get("SERS_NAME", ""),
            "prohibt_content": row.get("PROHBT_CONTENT", ""),
            "remark": row.get("REMARK", ""),
            "notification_date": str(row.get("NOTIFICATION_DATE", "")),
        }
        for _, row in df.iterrows()
    ]

    insert_bulk(DurDuplicate, data)


if __name__ == "__main__":
    import_drug_items()
    import_drug_details()
    import_easy_drug()
    import_dur_interactions()
    import_dur_duplicates()

    print("데이터 적재 완료")