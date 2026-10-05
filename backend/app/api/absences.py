from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Absence, Candidate, Hall

router = APIRouter(prefix="/absences", tags=["absences"])


class AbsenceIn(BaseModel):
    hall_id: int = 1
    candidate_ids: list[int]


def _absent_rows(db: Session, hall_id: int) -> list[dict]:
    rows = db.scalars(
        select(Absence).where(Absence.hall_id == hall_id).order_by(Absence.id)).all()
    return [{"id": a.id, "hall_id": a.hall_id, "candidate_id": a.candidate_id,
             "reason": a.reason} for a in rows]


@router.get("")
def list_absences(hall_id: int = 1, db: Session = Depends(get_db)):
    if not db.get(Hall, hall_id):
        raise HTTPException(404, "考室不存在")
    return _absent_rows(db, hall_id)


@router.post("")
def set_absences(body: AbsenceIn, db: Session = Depends(get_db)):
    """全量设置某考室的缺考名单（配置，不触发排座）。未配置即为缺考 0。"""
    hall = db.get(Hall, body.hall_id)
    if not hall:
        raise HTTPException(404, "考室不存在")
    valid = set(db.scalars(
        select(Candidate.id).where(Candidate.hall_id == body.hall_id)).all())
    bad = [cid for cid in body.candidate_ids if cid not in valid]
    if bad:
        raise HTTPException(400, f"考生不属于该考室或不存在: {bad}")
    for a in db.scalars(select(Absence).where(Absence.hall_id == body.hall_id)).all():
        db.delete(a)
    for cid in dict.fromkeys(body.candidate_ids):  # 去重保序
        db.add(Absence(hall_id=body.hall_id, candidate_id=cid))
    db.commit()
    return _absent_rows(db, body.hall_id)
