from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, desc
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


@router.get("/me/activity")
def get_activity(
    user_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = (
        select(SLHLedger)
        .where(SLHLedger.user_id == user_id)
        .order_by(desc(SLHLedger.id))
        .limit(limit)
    )
    rows = db.execute(q).scalars().all()

    out: List[Dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": r.id,
                "ts": r.created_at.isoformat(),
                "amount_slh": str(r.amount_slh),
                "reason": r.reason,
                "ref_type": r.ref_type,
                "ref_id": r.ref_id,
            }
        )

    return {
        "user_id": user_id,
        "slh_balance": str(slh_balance(db, user_id)),
        "items": out,
        "count": len(out),
    }


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

    db.add(
        SLHLedger(
            user_id=d.user_id,
            amount_slh=minted,
            reason="deposit_reward",
            ref_type="deposit",
            ref_id=d.id,
        )
    )

    db.commit()
    return {
        "status": "ok",
        "deposit_id": d.id,
        "minted_slh": str(minted),
        "new_balance": str(slh_balance(db, d.user_id)),
    }


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
    r.decided_by_admin = req.admin_id
    r.decided_at = datetime.utcnow()

    db.add(
        SLHLedger(
            user_id=r.user_id,
            amount_slh=Decimal("0") - r.slh_amount,
            reason="redeem",
            ref_type="redeem",
            ref_id=r.id,
        )
    )

    db.commit()
    return {
        "status": "ok",
        "redeem_id": r.id,
        "debited_slh": str(r.slh_amount),
        "new_balance": str(slh_balance(db, r.user_id)),
    }


@router.get("/admin/deposits")
def admin_list_deposits(
    status: str = Query(default="pending"),
    user_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    if user_id is None:
        q = select(Deposit).where(Deposit.status == status).order_by(desc(Deposit.id)).limit(limit)
    else:
        q = select(Deposit).where(Deposit.status == status, Deposit.user_id == user_id).order_by(desc(Deposit.id)).limit(limit)

    items = db.execute(q).scalars().all()
    return {
        "status": status,
        "count": len(items),
        "items": [
            {
                "deposit_id": d.id,
                "user_id": d.user_id,
                "amount_ils": str(d.amount_ils),
                "method": d.method,
                "reference": d.reference,
                "notes": d.notes,
                "state": d.status,
                "created_at": d.created_at.isoformat(),
                "confirmed_at": (d.confirmed_at.isoformat() if d.confirmed_at else None),
            }
            for d in items
        ],
    }


@router.get("/admin/redeems")
def admin_list_redeems(
    status: str = Query(default="requested"),
    user_id: Optional[int] = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    if user_id is None:
        q = select(RedemptionRequest).where(RedemptionRequest.status == status).order_by(desc(RedemptionRequest.id)).limit(limit)
    else:
        q = (
            select(RedemptionRequest)
            .where(RedemptionRequest.status == status, RedemptionRequest.user_id == user_id)
            .order_by(desc(RedemptionRequest.id))
            .limit(limit)
        )

    items = db.execute(q).scalars().all()
    return {
        "status": status,
        "count": len(items),
        "items": [
            {
                "redeem_id": r.id,
                "user_id": r.user_id,
                "slh_amount": str(r.slh_amount),
                "target": r.target,
                "notes": r.notes,
                "state": r.status,
                "created_at": r.created_at.isoformat(),
                "decided_at": (r.decided_at.isoformat() if r.decided_at else None),
                "decided_by_admin": r.decided_by_admin,
            }
            for r in items
        ],
    }