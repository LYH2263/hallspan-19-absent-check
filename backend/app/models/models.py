from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.constants import ABSENT_RETAIN, ABSENT_RELEASE, ABSENT_STRATEGIES, DEFAULT_ABSENT_STRATEGY
from app.database import Base

# 缺考占格策略（与排座引擎同一口径，常量见 app.constants）：
#   retain  —— 缺考占格保留：缺考者保留座位、计入占格，不再算未排
#   release —— 释放策略：缺考不占格，其座位放空、该考生计入未排


class Hall(Base):
    __tablename__ = "halls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    rows: Mapped[int] = mapped_column(Integer)
    cols: Mapped[int] = mapped_column(Integer)
    min_manhattan: Mapped[int] = mapped_column(Integer, default=2)
    absent_strategy: Mapped[str] = mapped_column(String(16), default=DEFAULT_ABSENT_STRATEGY)


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


class Absentee(Base):
    """缺考名单：一个考生至多登记一次缺考。"""
    __tablename__ = "absentees"
    __table_args__ = (UniqueConstraint("candidate_id", name="uq_absentee_candidate"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    marked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SeatPlan(Base):
    """一张排座方案。voided_at 非空表示已作废，不再是当前有效方案。"""
    __tablename__ = "seat_plans"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    hall_id: Mapped[int] = mapped_column(ForeignKey("halls.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    result_json: Mapped[str] = mapped_column(Text, default="{}")
