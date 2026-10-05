import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ABSENT_STRATEGIES, Absentee, Candidate, Hall, SeatPlan
from app.services.seat_engine import normalize_snapshot, register_view, seat_snapshot

router = APIRouter(prefix="/seating", tags=["seating"])


class NoEffectivePlan(HTTPException):
    def __init__(self, hall_id: int):
        super().__init__(status_code=404, detail={"code": "no_effective_plan",
                                                  "message": "尚无有效排座方案，请先在排座图执行排座",
                                                  "hall_id": hall_id})


def _hall_or_404(db: Session, hall_id: int) -> Hall:
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "考室不存在")
    return hall


def _absent_ids(db: Session, hall_id: int) -> set[int]:
    return set(db.scalars(select(Absentee.candidate_id).where(Absentee.hall_id == hall_id)).all())


def _candidates(db: Session, hall_id: int) -> list[dict]:
    rows = db.scalars(select(Candidate).where(Candidate.hall_id == hall_id).order_by(Candidate.id)).all()
    return [{"id": c.id, "name": c.name, "ticket_no": c.ticket_no, "paper_id": c.paper_id} for c in rows]


def effective_plan(db: Session, hall_id: int) -> SeatPlan | None:
    """当前有效方案：该考室最新一张未作废方案。唯一指针，所有视图共用。"""
    return db.scalars(
        select(SeatPlan)
        .where(SeatPlan.hall_id == hall_id, SeatPlan.voided_at.is_(None))
        .order_by(SeatPlan.id.desc())
    ).first()


def _require_effective(db: Session, hall_id: int) -> SeatPlan:
    plan = effective_plan(db, hall_id)
    if not plan:
        raise NoEffectivePlan(hall_id)
    return plan


def _payload(plan: SeatPlan) -> dict:
    data = _snapshot(plan)
    return {"id": plan.id, "plan_id": plan.id, "voided": plan.voided_at is not None, **data}


def _snapshot(plan: SeatPlan) -> dict:
    return normalize_snapshot(json.loads(plan.result_json))


def _build_snapshot(db: Session, hall: Hall) -> dict:
    cands = _candidates(db, hall.id)
    absent_ids = _absent_ids(db, hall.id)
    hall_info = {"id": hall.id, "name": hall.name, "min_manhattan": hall.min_manhattan,
                 "absent_strategy": hall.absent_strategy}
    # seat_snapshot 内部执行 reconcile：口径对不齐会直接抛错，绝不静默凑数。
    return seat_snapshot(hall.rows, hall.cols, hall.min_manhattan, cands,
                         absent_ids, hall.absent_strategy, hall=hall_info)


@router.post("/run")
def run_seating(hall_id: int = 1, db: Session = Depends(get_db)):
    """显式排座：生成一张新的有效方案（显式动作，非打开任何只读页面触发）。"""
    hall = _hall_or_404(db, hall_id)
    result = _build_snapshot(db, hall)
    plan = SeatPlan(hall_id=hall_id, voided_at=None, created_at=datetime.utcnow(),
                    result_json=json.dumps(result, ensure_ascii=False))
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return _payload(plan)


@router.get("/effective")
def get_effective(hall_id: int = 1, db: Session = Depends(get_db)):
    """读取当前有效方案；不存在返回 404，绝不为此生成新方案。"""
    _hall_or_404(db, hall_id)
    return _payload(_require_effective(db, hall_id))


@router.get("/register")
def get_register(hall_id: int = 1, db: Session = Depends(get_db)):
    """缺考核对册（只读）：已到 / 缺考 / 未排，全部从当前有效方案的同一份快照派生。

    - 不生成、不写入、不 commit：打开核对册不会新增任何方案条数。
    - register_view 内部再核对计数；与统计/排座图/违规对不齐即失败。
    """
    _hall_or_404(db, hall_id)
    plan = _require_effective(db, hall_id)
    snapshot = _snapshot(plan)
    view = register_view(snapshot)
    return {"hall_id": hall_id, "plan_id": plan.id, **view}


@router.get("/violations")
def violations(hall_id: int = 1, db: Session = Depends(get_db)):
    _hall_or_404(db, hall_id)
    plan = _require_effective(db, hall_id)
    data = _snapshot(plan)
    return {"hall_id": hall_id, "plan_id": plan.id,
            "violations": data.get("violations", []), "unplaced": data.get("unplaced", [])}


@router.get("/stats")
def stats(hall_id: int = 1, db: Session = Depends(get_db)):
    _hall_or_404(db, hall_id)
    plan = _require_effective(db, hall_id)
    data = _snapshot(plan)
    return {"hall_id": hall_id, "plan_id": plan.id, **data.get("stats", {})}


@router.get("/plans")
def list_plans(hall_id: int = 1, db: Session = Depends(get_db)):
    """方案列表与作废状态，供切换/查看当前指针。"""
    _hall_or_404(db, hall_id)
    plans = db.scalars(
        select(SeatPlan).where(SeatPlan.hall_id == hall_id).order_by(SeatPlan.id.desc())
    ).all()
    eff = effective_plan(db, hall_id)
    eff_id = eff.id if eff else None
    return [
        {"id": p.id, "created_at": p.created_at.isoformat() if p.created_at else None,
         "voided": p.voided_at is not None,
         "voided_at": p.voided_at.isoformat() if p.voided_at else None,
         "effective": p.id == eff_id}
        for p in plans
    ]


def _get_plan_or_404(db: Session, plan_id: int) -> SeatPlan:
    plan = db.get(SeatPlan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    return plan


@router.post("/{plan_id}/void")
def void_plan(plan_id: int, db: Session = Depends(get_db)):
    """作废一张方案。作废后当前指针自动落到次新的未作废方案，核对册随之跟新。"""
    plan = _get_plan_or_404(db, plan_id)
    if plan.voided_at is None:
        plan.voided_at = datetime.utcnow()
        db.commit()
    return {"id": plan.id, "voided": True, "voided_at": plan.voided_at.isoformat()}


@router.post("/{plan_id}/reinstate")
def reinstate_plan(plan_id: int, db: Session = Depends(get_db)):
    """恢复一张已作废方案；若其为最新的未作废方案则重新成为当前有效方案。"""
    plan = _get_plan_or_404(db, plan_id)
    if plan.voided_at is not None:
        plan.voided_at = None
        db.commit()
    return {"id": plan.id, "voided": False}
