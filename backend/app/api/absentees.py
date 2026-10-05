from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Absentee, Candidate, Hall

router = APIRouter(prefix="/absentees", tags=["absentees"])


class AbsentBody(BaseModel):
    candidate_id: int


def _candidate(db: Session, candidate_id: int) -> Candidate:
    cand = db.get(Candidate, candidate_id)
    if not cand:
        raise HTTPException(404, "考生不存在")
    return cand


@router.get("")
def list_absentees(hall_id: int = 1, db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Absentee).where(Absentee.hall_id == hall_id).order_by(Absentee.id)
    ).all()
    return [{"id": a.id, "candidate_id": a.candidate_id, "hall_id": a.hall_id,
             "marked_at": a.marked_at.isoformat() if a.marked_at else None} for a in rows]


@router.post("")
def mark_absent(body: AbsentBody, db: Session = Depends(get_db)):
    """登记缺考（幂等）。只更新缺考名单，不会因此生成或改动任何排座方案。"""
    cand = _candidate(db, body.candidate_id)
    exists = db.scalars(
        select(Absentee).where(Absentee.candidate_id == body.candidate_id)
    ).first()
    if exists:
        return {"id": exists.id, "candidate_id": exists.candidate_id, "hall_id": exists.hall_id}
    rec = Absentee(candidate_id=cand.id, hall_id=cand.hall_id)
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return {"id": rec.id, "candidate_id": rec.candidate_id, "hall_id": rec.hall_id}


@router.delete("/{candidate_id}")
def clear_absent(candidate_id: int, db: Session = Depends(get_db)):
    _candidate(db, candidate_id)
    rec = db.scalars(select(Absentee).where(Absentee.candidate_id == candidate_id)).first()
    if rec:
        db.delete(rec)
        db.commit()
    return {"candidate_id": candidate_id, "absent": False}
