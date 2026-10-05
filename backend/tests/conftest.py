import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SEED_ON_EMPTY", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.models import Candidate, Hall, PaperSet


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


def make_hall(db, *, rows=5, cols=6, min_manhattan=2, strategy="retain", n=12, papers=3):
    hall = Hall(code="H101", name="一号考室", rows=rows, cols=cols,
                min_manhattan=min_manhattan, absent_strategy=strategy)
    db.add(hall)
    db.flush()
    paper_ids = []
    for i in range(papers):
        p = PaperSet(code=f"P-{i}", title=f"卷{i}")
        db.add(p)
        db.flush()
        paper_ids.append(p.id)
    for i in range(n):
        db.add(Candidate(hall_id=hall.id, name=f"考生{i}", ticket_no=f"T{2026001+i}",
                         paper_id=paper_ids[i % papers]))
    db.commit()
    return hall
