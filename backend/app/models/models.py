from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Hall(Base):
    __tablename__ = "halls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    rows: Mapped[int] = mapped_column(Integer)
    cols: Mapped[int] = mapped_column(Integer)
    min_manhattan: Mapped[int] = mapped_column(Integer, default=2)
    # 缺考策略（与 08 策略口径一致）：
    #   True  -> 缺考占格保留：缺考考生占一个格子，计入占格，不得记入未排
    #   False -> 释放策略：缺考不占格，也不计入未排
    reserve_absent_seat: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # 指向当前有效方案（同一张方案供排座图 / 违规 / 统计 / 核对册读取）。
    # 应用层维护的指针（不建库外键，避免 halls↔seat_plans 循环依赖）。
    active_plan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

class PaperSet(Base):
    __tablename__ = "paper_sets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    title: Mapped[str] = mapped_column(String(128))

class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    name: Mapped[str] = mapped_column(String(64))
    ticket_no: Mapped[str] = mapped_column(String(32))
    paper_id: Mapped[int] = mapped_column(ForeignKey("paper_sets.id"))

class Absence(Base):
    """缺考配置（按考生）。排座时读取并冻结进方案快照；未配置时缺考为 0。"""
    __tablename__ = "absences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), unique=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class SeatPlan(Base):
    __tablename__ = "seat_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    voided: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
