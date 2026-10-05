import json
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.models import Absence, Candidate, Hall, PaperSet, SeatPlan
from app.services.seat_engine import build_plan


def seed_if_empty(db: Session) -> None:
    if (db.scalar(select(func.count()).select_from(Hall)) or 0) > 0:
        return
    # 默认采用释放策略（缺考不占格）；未配缺考时册上缺考为 0。
    hall = Hall(code="H101", name="一号考室", rows=5, cols=6, min_manhattan=2,
                reserve_absent_seat=False)
    db.add(hall); db.flush()
    papers = [("P-A", "语文 A 卷"), ("P-B", "语文 B 卷"), ("P-C", "语文 C 卷")]
    paper_ids = []
    for code, title in papers:
        p = PaperSet(code=code, title=title)
        db.add(p); db.flush()
        paper_ids.append(p.id)
    names = ["陈一", "李二", "张三", "赵四", "钱五", "孙六", "周七", "吴八", "郑九", "王十", "冯十一", "陈十二"]
    for i, name in enumerate(names):
        db.add(Candidate(hall_id=hall.id, name=name, ticket_no=f"T{2026001+i}",
                         paper_id=paper_ids[i % len(paper_ids)]))
    db.flush()

    # 种子排完：直接生成当前有效方案并落指针，使核对册 / 统计开箱同数。
    cands = [{"id": c.id, "name": c.name, "ticket_no": c.ticket_no, "paper_id": c.paper_id}
             for c in db.scalars(select(Candidate).where(Candidate.hall_id == hall.id)).all()]
    absent_ids = set(db.scalars(
        select(Absence.candidate_id).where(Absence.hall_id == hall.id)).all())
    result = build_plan(hall.rows, hall.cols, hall.min_manhattan, cands,
                        absent_ids=absent_ids, reserve_absent=hall.reserve_absent_seat)
    result["hall"] = {"id": hall.id, "name": hall.name,
                      "min_manhattan": hall.min_manhattan,
                      "reserve_absent_seat": hall.reserve_absent_seat}
    plan = SeatPlan(hall_id=hall.id, voided=False, created_at=datetime.utcnow(),
                    result_json=json.dumps(result, ensure_ascii=False))
    db.add(plan); db.flush()
    hall.active_plan_id = plan.id
    db.commit()
