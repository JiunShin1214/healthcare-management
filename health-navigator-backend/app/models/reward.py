from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.core.database import Base


class RewardProduct(Base):
    __tablename__ = "reward_products"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False)
    brand = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    price_points = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PointTransaction(Base):
    __tablename__ = "point_transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(20), nullable=False)  # earn / spend
    amount = Column(Integer, nullable=False)
    reason = Column(String(100), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RewardPurchase(Base):
    __tablename__ = "reward_purchases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("reward_products.id"), nullable=False)
    price_points = Column(Integer, nullable=False)
    status = Column(String(30), nullable=False, default="purchased")
    coupon_code = Column(String(100), nullable=False)
    purchased_at = Column(DateTime(timezone=True), server_default=func.now())