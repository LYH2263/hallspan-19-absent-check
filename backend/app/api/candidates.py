from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Absentee, Candidate

router = APIRouter(prefix="/candidates", tags=["candidates"])


@router.get("")
def list_candidates(db: Session = Depends(get_db)):
    rows = db.scalars(select(Candidate).order_by(Candidate.id)).all()
    absent_ids = set(db.scalars(select(Absentee.candidate_id)).all())
    return [{"id": r.id, "hall_id": r.hall_id, "name": r.name, "ticket_no": r.ticket_no,
             "paper_id": r.paper_id, "absent": r.id in absent_ids}
            for r in rows]
