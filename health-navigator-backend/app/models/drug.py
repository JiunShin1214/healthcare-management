from sqlalchemy import Column, String, Text, Integer, Index

from app.core.database import Base


class DrugItem(Base):
    __tablename__ = "drug_items"

    item_seq = Column(String(50), primary_key=True, index=True)
    item_name = Column(String(500), nullable=False, index=True)
    entp_name = Column(String(255), nullable=True)

    item_eng_name = Column(String(500), nullable=True)
    entp_eng_name = Column(String(255), nullable=True)

    ingredient_name = Column(Text, nullable=True)
    ingredient_count = Column(String(50), nullable=True)

    product_type = Column(String(255), nullable=True)
    etc_otc = Column(String(100), nullable=True)
    image_url = Column(Text, nullable=True)

    cancel_name = Column(String(100), nullable=True)
    permit_date = Column(String(50), nullable=True)
    edi_code = Column(Text, nullable=True)


class DrugDetail(Base):
    __tablename__ = "drug_details"

    item_seq = Column(String(50), primary_key=True, index=True)
    item_name = Column(String(500), nullable=True)
    entp_name = Column(String(255), nullable=True)

    item_eng_name = Column(String(500), nullable=True)
    entp_eng_name = Column(String(255), nullable=True)

    main_item_ingr = Column(Text, nullable=True)
    main_ingr_eng = Column(Text, nullable=True)

    chart = Column(Text, nullable=True)
    storage_method = Column(Text, nullable=True)
    valid_term = Column(Text, nullable=True)
    pack_unit = Column(Text, nullable=True)

    ee_doc_data = Column(Text, nullable=True)
    ud_doc_data = Column(Text, nullable=True)
    nb_doc_data = Column(Text, nullable=True)

    atc_code = Column(String(100), nullable=True, index=True)
    edi_code = Column(Text, nullable=True)

    etc_otc_code = Column(String(100), nullable=True)
    cancel_name = Column(String(100), nullable=True)
    permit_date = Column(String(50), nullable=True)


class EasyDrug(Base):
    __tablename__ = "easy_drugs"

    item_seq = Column(String(50), primary_key=True, index=True)
    item_name = Column(String(500), nullable=True)
    entp_name = Column(String(255), nullable=True)

    effect = Column(Text, nullable=True)
    use_method = Column(Text, nullable=True)
    warning = Column(Text, nullable=True)
    caution = Column(Text, nullable=True)
    side_effect = Column(Text, nullable=True)
    interaction = Column(Text, nullable=True)
    deposit_method = Column(Text, nullable=True)

    image_url = Column(Text, nullable=True)
    open_date = Column(String(50), nullable=True)
    update_date = Column(String(50), nullable=True)


class DurInteraction(Base):
    __tablename__ = "dur_interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    dur_seq = Column(String(100), nullable=True, index=True)
    type_name = Column(String(100), nullable=True, index=True)

    item_seq = Column(String(50), nullable=True, index=True)
    item_name = Column(String(500), nullable=True)
    entp_name = Column(String(255), nullable=True)

    ingr_code = Column(String(100), nullable=True, index=True)
    ingr_name = Column(String(255), nullable=True)

    mixture_item_seq = Column(String(50), nullable=True, index=True)
    mixture_item_name = Column(String(500), nullable=True)
    mixture_entp_name = Column(String(255), nullable=True)

    mixture_ingr_code = Column(String(100), nullable=True, index=True)
    mixture_ingr_name = Column(String(255), nullable=True)

    prohibt_content = Column(Text, nullable=True)
    remark = Column(Text, nullable=True)
    notification_date = Column(String(50), nullable=True)


class DurDuplicate(Base):
    __tablename__ = "dur_duplicates"

    id = Column(Integer, primary_key=True, autoincrement=True)

    dur_seq = Column(String(100), nullable=True, index=True)
    type_name = Column(String(100), nullable=True, index=True)

    item_seq = Column(String(50), nullable=True, index=True)
    item_name = Column(String(500), nullable=True)
    entp_name = Column(String(255), nullable=True)

    ingr_code = Column(String(100), nullable=True, index=True)
    ingr_name = Column(String(255), nullable=True)
    ingr_eng_name = Column(Text, nullable=True)

    effect_name = Column(String(255), nullable=True, index=True)
    sers_name = Column(String(255), nullable=True)

    prohibt_content = Column(Text, nullable=True)
    remark = Column(Text, nullable=True)
    notification_date = Column(String(50), nullable=True)


Index("ix_dur_interaction_item_pair", DurInteraction.item_seq, DurInteraction.mixture_item_seq)
Index("ix_dur_interaction_ingr_pair", DurInteraction.ingr_code, DurInteraction.mixture_ingr_code)
Index("ix_dur_duplicate_item_effect", DurDuplicate.item_seq, DurDuplicate.effect_name)