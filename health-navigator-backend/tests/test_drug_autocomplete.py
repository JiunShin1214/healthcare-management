from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.drug import DrugItem
from app.services.drug_service_db import autocomplete_drugs


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def add_drug(db, item_seq, item_name, cancel_name="정상"):
    db.add(
        DrugItem(
            item_seq=item_seq,
            item_name=item_name,
            entp_name="테스트제약",
            cancel_name=cancel_name,
        )
    )
    db.commit()


def test_autocomplete_returns_empty_list_for_blank_query():
    db = make_session()
    try:
        add_drug(db, "1", "타이레놀정")
        assert autocomplete_drugs(db, q="") == []
    finally:
        db.close()


def test_autocomplete_returns_matching_active_drugs_only():
    db = make_session()
    try:
        add_drug(db, "1", "타이레놀정")
        add_drug(db, "2", "타이레놀콜드정")
        add_drug(db, "3", "취소된타이레놀", cancel_name="취소")

        results = autocomplete_drugs(db, q="타이레", limit=10)

        assert [item["itemSeq"] for item in results] == ["1", "2"]
        assert all(set(item.keys()) == {"itemSeq", "itemName", "entpName"} for item in results)
    finally:
        db.close()


def test_autocomplete_clamps_limit_to_twenty():
    db = make_session()
    try:
        for index in range(25):
            add_drug(db, str(index), f"타이레놀{index:02d}")

        results = autocomplete_drugs(db, q="타이레", limit=100)

        assert len(results) == 20
    finally:
        db.close()
