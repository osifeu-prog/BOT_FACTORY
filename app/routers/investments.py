from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_investments import Deposit, SLHLedger, RedemptionRequest

router = APIRouter(prefix="/invest", tags=["invest"])


class DepositRequestIn(BaseModel):
    user_id: int
    amount_ils: Decimal = Field(gt=0)
    method: str = "bank"
    reference: Optional[str] = None
    notes: Optional[str] = None


class AdminConfirmDepositIn(BaseModel):
    deposit_id: int
    slh_per_ils: Decimal = Field(default=Decimal("1.0"), gt=0)
    admin_id: int = 0


class RedeemRequestIn(BaseModel):
    user_id: int
    slh_amount: Decimal = Field(gt=0)
    target: Optional[str] = None
    notes: Optional[str] = None


class AdminApproveRedeemIn(BaseModel):
    redeem_id: int
    admin_id: int = 0


def slh_balance(db: Session, user_id: int) -> Decimal:
    q = select(func.coalesce(func.sum(SLHLedger.amount_slh), 0)).where(SLHLedger.user_id == user_id)
    return Decimal(str(db.execute(q).scalar_one()))


@router.post("/deposit/request")
def create_deposit(req: DepositRequestIn, db: Session = Depends(get_db)):
    d = Deposit(
        user_id=req.user_id,
        amount_ils=req.amount_ils,
        method=req.method,
        reference=req.reference,
        notes=req.notes,
        status="pending",
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return {"status": "ok", "deposit_id": d.id, "state": d.status}


@router.get("/me/slh_balance")
def get_slh_balance(user_id: int, db: Session = Depends(get_db)):
    return {"user_id": user_id, "slh_balance": str(slh_balance(db, user_id))}


@router.post("/redeem/request")
def create_redeem(req: RedeemRequestIn, db: Session = Depends(get_db)):
    bal = slh_balance(db, req.user_id)
    if req.slh_amount > bal:
        raise HTTPException(status_code=400, detail=f"Insufficient SLH. balance={bal}")

    r = RedemptionRequest(
        user_id=req.user_id,
        slh_amount=req.slh_amount,
        target=req.target,
        notes=req.notes,
        status="requested",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return {"status": "ok", "redeem_id": r.id, "state": r.status}


@router.post("/admin/deposit/confirm")
def admin_confirm_deposit(req: AdminConfirmDepositIn, db: Session = Depends(get_db)):
    d = db.get(Deposit, req.deposit_id)
    if not d:
        raise HTTPException(status_code=404, detail="Deposit not found")
    if d.status != "pending":
        raise HTTPException(status_code=400, detail=f"Deposit not pending (status={d.status})")

    d.status = "confirmed"
    d.confirmed_at = datetime.utcnow()

    minted = (d.amount_ils * req.slh_per_ils)
    db.add(SLHLedger(
        user_id=d.user_id,
        amount_slh=minted,
        reason="deposit_reward",
        ref_type="deposit",
        ref_id=d.id,
    ))

    db.commit()
    return {"status": "ok", "deposit_id": d.id, "minted_slh": str(minted)}


@router.post("/admin/redeem/approve")
def admin_approve_redeem(req: AdminApproveRedeemIn, db: Session = Depends(get_db)):
    r = db.get(RedemptionRequest, req.redeem_id)
    if not r:
        raise HTTPException(status_code=404, detail="Redeem request not found")
    if r.status != "requested":
        raise HTTPException(status_code=400, detail=f"Redeem not requested (status={r.status})")

    bal = slh_balance(db, r.user_id)
    if r.slh_amount > bal:
        raise HTTPException(status_code=400, detail=f"Insufficient SLH at approval time. balance={bal}")

    r.status = "approved"
    r.decided_at = datetime.utcnow()
    r.decided_by_admin = req.admin_id

    db.add(SLHLedger(
        user_id=r.user_id,
        amount_slh=Decimal("0") - r.slh_amount,
        reason="redeem",
        ref_type="redeem",
        ref_id=r.id,
    ))

    db.commit()
    return {"status": "ok", "redeem_id": r.id, "debited_slh": str(r.slh_amount)}
# redeploy ping 2025-12-30T14:56:35.5334217+02:00

