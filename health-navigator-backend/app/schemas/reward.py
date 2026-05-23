from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class RewardProductResponse(BaseModel):
    id: int
    category: str
    brand: str
    name: str
    price_points: int
    description: Optional[str] = None
    image_url: Optional[str] = None

    class Config:
        from_attributes = True


class PointResponse(BaseModel):
    points: int


class PointUpdateRequest(BaseModel):
    change: int
    reason: str = "manual"


class PurchaseRequest(BaseModel):
    product_id: int


class PurchaseResponse(BaseModel):
    success: bool
    message: str
    remaining_points: int
    coupon_code: Optional[str] = None


class PurchaseHistoryResponse(BaseModel):
    id: int
    product_id: int
    price_points: int
    status: str
    coupon_code: str
    purchased_at: datetime

    class Config:
        from_attributes = True