import uuid
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.routers.auth import get_current_user
from app.models.user import User
from app.models.reward import RewardProduct, PointTransaction, RewardPurchase
from app.schemas.reward import (
    RewardProductResponse,
    PointResponse,
    PointUpdateRequest,
    PurchaseRequest,
    PurchaseResponse,
    PurchaseHistoryResponse,
)

router = APIRouter(prefix="/rewards", tags=["Rewards"])


@router.get("/products", response_model=List[RewardProductResponse])
def get_reward_products(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(RewardProduct).filter(RewardProduct.is_active == True)

    if category:
        query = query.filter(RewardProduct.category == category)

    return query.order_by(RewardProduct.id.asc()).all()


@router.get("/me/points", response_model=PointResponse)
def get_my_points(
    current_user: User = Depends(get_current_user),
):
    return {"points": current_user.points}


@router.post("/me/points", response_model=PointResponse)
def update_my_points(
    request: PointUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    new_points = current_user.points + request.change

    if new_points < 0:
        raise HTTPException(status_code=400, detail="포인트가 부족합니다.")

    current_user.points = new_points

    transaction_type = "earn" if request.change >= 0 else "spend"

    transaction = PointTransaction(
        user_id=current_user.id,
        type=transaction_type,
        amount=request.change,
        reason=request.reason,
    )

    db.add(transaction)
    db.commit()
    db.refresh(current_user)

    return {"points": current_user.points}


@router.post("/purchase", response_model=PurchaseResponse)
def purchase_reward(
    request: PurchaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = (
        db.query(RewardProduct)
        .filter(
            RewardProduct.id == request.product_id,
            RewardProduct.is_active == True,
        )
        .first()
    )

    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")

    if current_user.points < product.price_points:
        return PurchaseResponse(
            success=False,
            message="포인트가 부족합니다.",
            remaining_points=current_user.points,
            coupon_code=None,
        )

    current_user.points -= product.price_points

    coupon_code = f"HN-{uuid.uuid4().hex[:10].upper()}"

    purchase = RewardPurchase(
        user_id=current_user.id,
        product_id=product.id,
        price_points=product.price_points,
        status="purchased",
        coupon_code=coupon_code,
    )

    transaction = PointTransaction(
        user_id=current_user.id,
        type="spend",
        amount=-product.price_points,
        reason=f"purchase:{product.id}",
    )

    db.add(purchase)
    db.add(transaction)
    db.commit()
    db.refresh(current_user)

    return PurchaseResponse(
        success=True,
        message="구매가 완료되었습니다.",
        remaining_points=current_user.points,
        coupon_code=coupon_code,
    )


@router.get("/me/purchases", response_model=List[PurchaseHistoryResponse])
def get_my_purchases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(RewardPurchase)
        .filter(RewardPurchase.user_id == current_user.id)
        .order_by(RewardPurchase.purchased_at.desc())
        .all()
    )