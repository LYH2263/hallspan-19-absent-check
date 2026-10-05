import os

os.environ.setdefault("DATABASE_URL", "sqlite://")  # 测试用 SQLite，无需 Postgres/psycopg2

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Candidate, Hall, PaperSet
from fastapi.testclient import TestClient


@pytest.fixture
def db_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_factory):
    # 不使用上下文管理器，避免触发连往 Postgres 的 lifespan；库表已由 fixture 建好。
    return TestClient(app)


@pytest.fixture
def make_hall(db_factory):
    def _make(rows=5, cols=6, min_manhattan=2, reserve=False, n=12):
        db = db_factory()
        hall = Hall(code=f"H{rows}x{cols}{'R' if reserve else 'L'}-{n}", name="考室",
                    rows=rows, cols=cols, min_manhattan=min_manhattan,
                    reserve_absent_seat=reserve)
        db.add(hall); db.flush()
        db.add(hall); db.flush()
        for i in range(n):
            # 每名考生独立试卷套，避免同卷相邻规则干扰，纯看容量与缺考策略。
            p = PaperSet(code=f"P-{rows}-{cols}-{i}", title=f"卷{i}")
            db.add(p); db.flush()
            db.add(Candidate(hall_id=hall.id, name=f"考生{i}", ticket_no=f"T{1000+i}",
                             paper_id=p.id))
        db.commit()
        hid = hall.id
        db.close()
        return hid
    return _make
