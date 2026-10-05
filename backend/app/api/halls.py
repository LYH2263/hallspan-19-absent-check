from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ABSENT_STRATEGIES, Hall

router = APIRouter(prefix="/halls", tags=["halls"])


class StrategyBody(BaseModel):
    absent_strategy: str


@router.get("")
def list_halls(db: Session = Depends(get_db)):
    return [{"id": r.id, "code": r.code, "name": r.name, "rows": r.rows, "cols": r.cols,
             "min_manhattan": r.min_manhattan, "absent_strategy": r.absent_strategy}
            for r in db.scalars(select(Hall).order_by(Hall.id)).all()]


@router.patch("/{hall_id}/strategy")
def set_strategy(hall_id: int, body: StrategyBody, db: Session = Depends(get_db)):
    """切换缺考占格策略（retain 占格保留 / release 释放）。只改配置，不生成方案。

    切换后需重新执行排座，新方案才按新口径占格；历史方案保留原快照口径。
    """
    if body.absent_strategy not in ABSENT_STRATEGIES:
        raise HTTPException(422, f"缺考占格策略须为 {ABSENT_STRATEGIES} 之一")
    hall = db.get(Hall, hall_id)
    if not hall:
        raise HTTPException(404, "考室不存在")
    hall.absent_strategy = body.absent_strategy
    db.commit()
    db.refresh(hall)
    return {"id": hall.id, "absent_strategy": hall.absent_strategy}
