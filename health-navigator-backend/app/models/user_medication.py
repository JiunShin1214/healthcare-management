from sqlalchemy import Column, Integer, String, Text, TIMESTAMP, ForeignKey, text
from sqlalchemy.orm import relationship

from app.core.database import Base


class UserMedication(Base):
    __tablename__ = "user_medications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    item_seq = Column(String(50), nullable=False, index=True)

    item_name = Column(String(500), nullable=False)
    entp_name = Column(String(255), nullable=True)

    memo = Column(Text, nullable=True)

    created_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )

    user = relationship("User")