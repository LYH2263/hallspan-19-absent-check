import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Absence, Candidate, Hall, SeatPlan
from app.services.seat_engine import build_plan

router = APIRouter(prefix="/seating", tags=["seating"])

NO_PLAN = "当前考室尚无有效方案，请先在排座图执行排座"


def _load_hall(db: Session, hall_id: int) -> Hall:
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "考室不存在")
    return hall


def _active_plan(db: Session, hall_id: int) -> tuple[Hall, SeatPlan, dict]:
    """返回当前有效方案及其快照。只读，绝不临时排座凑数。

    排座图 / 违规 / 统计 / 核对册全部经此读取同一指针；指针缺失或已作废即失败。
    """
    hall = _load_hall(db, hall_id)
    if not hall.active_plan_id:
        raise HTTPException(404, NO_PLAN)
    plan = db.get(SeatPlan, hall.active_plan_id)
    if not plan or plan.hall_id != hall_id:
        raise HTTPException(409, "当前指针指向的方案不存在")
    if plan.voided:
        raise HTTPException(409, "当前方案已作废，请切换有效方案")
    return hall, plan, json.loads(plan.result_json)


@router.post("/run")
def run_seating(hall_id: int = 1, db: Session = Depends(get_db)):
    """生成新方案并把当前指针指向它（唯一会新增方案的入口）。"""
    hall = _load_hall(db, hall_id)
    cands = [{"id": c.id, "name": c.name, "ticket_no": c.ticket_no, "paper_id": c.paper_id}
             for c in db.scalars(select(Candidate).where(Candidate.hall_id == hall_id)).all()]
    absent_ids = set(db.scalars(
        select(Absence.candidate_id).where(Absence.hall_id == hall_id)).all())
    try:
        result = build_plan(hall.rows, hall.cols, hall.min_manhattan, cands,
                            absent_ids=absent_ids, reserve_absent=hall.reserve_absent_seat)
    except (ValueError, AssertionError) as exc:
        raise HTTPException(400, f"排座口径核对失败：{exc}")
    result["hall"] = {"id": hall.id, "name": hall.name, "min_manhattan": hall.min_manhattan,
                      "reserve_absent_seat": hall.reserve_absent_seat}
    plan = SeatPlan(hall_id=hall_id, voided=False, created_at=datetime.utcnow(),
                    result_json=json.dumps(result, ensure_ascii=False))
    db.add(plan)
    db.flush()
    hall.active_plan_id = plan.id
    db.commit()
    db.refresh(plan)
    return {"id": plan.id, "plan_id": plan.id, **result}


@router.get("/plans")
def list_plans(hall_id: int = 1, db: Session = Depends(get_db)):
    hall = _load_hall(db, hall_id)
    plans = db.scalars(
        select(SeatPlan).where(SeatPlan.hall_id == hall_id).order_by(SeatPlan.id)).all()
    return [{"id": p.id, "created_at": p.created_at.isoformat() if p.created_at else None,
             "voided": p.voided, "active": p.id == hall.active_plan_id} for p in plans]


@router.post("/plans/{plan_id}/void")
def void_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.get(SeatPlan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    plan.voided = True
    # 保留指针，使各只读页明确报“当前方案已作废”（409），而不是被当成从未排座；
    # 切换到其它有效方案后指针即随之更新。
    db.commit()
    hall = db.get(Hall, plan.hall_id)
    return {"id": plan.id, "voided": True,
            "active_plan_id": hall.active_plan_id if hall else None}


@router.post("/plans/{plan_id}/activate")
def activate_plan(plan_id: int, db: Session = Depends(get_db)):
    """作废切换：把当前指针切到指定的有效（未作废）方案。"""
    plan = db.get(SeatPlan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    if plan.voided:
        raise HTTPException(409, "不能切换到已作废方案")
    hall = db.get(Hall, plan.hall_id)
    hall.active_plan_id = plan.id
    db.commit()
    return {"id": plan.id, "active_plan_id": plan.id}


@router.get("/latest")
def latest(hall_id: int = 1, db: Session = Depends(get_db)):
    _, plan, data = _active_plan(db, hall_id)
    return {"id": plan.id, "plan_id": plan.id, **data}


@router.get("/violations")
def violations(hall_id: int = 1, db: Session = Depends(get_db)):
    _, plan, data = _active_plan(db, hall_id)
    return {"plan_id": plan.id, "hall_id": hall_id,
            "violations": data.get("violations", []), "unplaced": data.get("unplaced", [])}


@router.get("/stats")
def stats(hall_id: int = 1, db: Session = Depends(get_db)):
    _, plan, data = _active_plan(db, hall_id)
    return {"plan_id": plan.id, "hall_id": hall_id, **data.get("stats", {})}


@router.get("/roster")
def roster(hall_id: int = 1, db: Session = Depends(get_db)):
    """缺考核对册（只读）。已到 / 缺考 / 未排全部取自当前有效方案的同一份快照，
    并与其中的统计块逐项核对；对不齐直接失败。打开本接口不会生成方案。"""
    hall, plan, data = _active_plan(db, hall_id)
    snap_stats = data.get("stats", {})

    rows: list[dict] = []
    for a in data.get("assignments", []):
        if a.get("absent"):
            continue  # 缺考占格统一由 absent 块给出，避免重复计数
        rows.append({"candidate_id": a["candidate_id"], "name": a["name"],
                     "ticket_no": a["ticket_no"], "paper_id": a["paper_id"],
                     "status": "present", "held": False,
                     "row": a["row"], "col": a["col"]})
    for ab in data.get("absent", []):
        held = bool(ab.get("held"))
        rows.append({"candidate_id": ab["id"], "name": ab["name"],
                     "ticket_no": ab["ticket_no"], "paper_id": ab["paper_id"],
                     "status": "absent", "held": held,
                     "row": ab.get("row"), "col": ab.get("col")})
    for u in data.get("unplaced", []):
        rows.append({"candidate_id": u["id"], "name": u["name"],
                     "ticket_no": u["ticket_no"], "paper_id": u["paper_id"],
                     "status": "unplaced", "held": False, "row": None, "col": None})

    present = sum(1 for r in rows if r["status"] == "present")
    absent = sum(1 for r in rows if r["status"] == "absent")
    absent_held = sum(1 for r in rows if r["status"] == "absent" and r["held"])
    unplaced = sum(1 for r in rows if r["status"] == "unplaced")
    summary = {
        "present": present,
        "seated": present,              # 已到 = 真正落座的到考人数
        "absent": absent,
        "absent_held": absent_held,
        "unplaced": unplaced,
        "violations": len(data.get("violations", [])),
        "capacity": snap_stats.get("capacity"),
        "occupied": present + absent_held,
        "roster_total": present + absent + unplaced,
        "reserve_absent_seat": bool(data.get("reserve_absent_seat")),
    }

    # —— 核对：册上口径必须与同一方案的统计 / 违规完全对齐，否则失败 ——
    def expect(key):
        if snap_stats.get(key) != summary[key]:
            raise HTTPException(500, f"核对册与统计对不齐：{key} "
                                    f"册={summary[key]} 统计={snap_stats.get(key)}")

    for key in ("seated", "absent", "absent_held", "unplaced", "capacity",
                "occupied", "roster_total", "reserve_absent_seat"):
        expect(key)
    if snap_stats.get("violations") != summary["violations"]:
        raise HTTPException(500, "核对册与违规数对不齐")
    # 占格策略：缺考须计入占格且不得入未排；释放策略：缺考不得占格
    if summary["reserve_absent_seat"]:
        if absent_held != absent:
            raise HTTPException(500, "占格策略下缺考未全部计入占格")
    elif absent_held != 0:
        raise HTTPException(500, "释放策略下缺考不应占格")

    return {
        "plan_id": plan.id,
        "hall_id": hall_id,
        "hall": {"id": hall.id, "name": hall.name},
        "summary": summary,
        "rows": rows,
    }
