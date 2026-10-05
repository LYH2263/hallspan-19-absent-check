from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Hall
router = APIRouter(prefix="/halls", tags=["halls"])

def _hall_dict(r: Hall) -> dict:
    return {"id": r.id, "code": r.code, "name": r.name, "rows": r.rows, "cols": r.cols,
            "min_manhattan": r.min_manhattan,
            "reserve_absent_seat": r.reserve_absent_seat,
            "active_plan_id": r.active_plan_id}

@router.get("")
def list_halls(db: Session = Depends(get_db)):
    return [_hall_dict(r) for r in db.scalars(select(Hall).order_by(Hall.id)).all()]


class HallPolicyIn(BaseModel):
    reserve_absent_seat: bool

@router.patch("/{hall_id}")
def update_hall_policy(hall_id: int, body: HallPolicyIn, db: Session = Depends(get_db)):
    """切换缺考策略（与 08 口径一致）。仅改配置，不排座、不删方案；
    需在排座图重新执行后，核对册才按新策略口径出数。"""
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "考室不存在")
    hall.reserve_absent_seat = body.reserve_absent_seat
    db.commit()
    return _hall_dict(hall)
