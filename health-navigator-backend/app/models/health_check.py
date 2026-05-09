from sqlalchemy import Boolean, Column, ForeignKey, Integer, JSON, String, Text, TIMESTAMP, text
from sqlalchemy.orm import relationship

from app.core.database import Base


class HealthCheckResult(Base):
    __tablename__ = "health_check_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    extracted_text = Column(Text, nullable=True)
    parsing_status = Column(String(50), nullable=True, index=True)
    missing_fields = Column(JSON, nullable=False)
    data = Column(JSON, nullable=False)
    original_data = Column(JSON, nullable=False)
    edited_data = Column(JSON, nullable=True)
    is_edited = Column(Boolean, nullable=False, server_default=text("FALSE"))

    created_at = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP"),
        nullable=False
    )
    updated_at = Column(
        TIMESTAMP,
        nullable=True,
        onupdate=text("CURRENT_TIMESTAMP")
    )

    user = relationship("User")
