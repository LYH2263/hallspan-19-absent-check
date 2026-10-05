from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.services.migrate import ensure_columns
from app.services.seat_engine import PlanReconcileError
from app.services.seed import seed_if_empty


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_columns(engine)
    if settings.seed_on_empty:
        db = SessionLocal()
        try:
            seed_if_empty(db)
        finally:
            db.close()
    yield


app = FastAPI(title="HallSpan", version="0.1.0", lifespan=lifespan)


@app.exception_handler(PlanReconcileError)
async def plan_reconcile_handler(_req: Request, exc: PlanReconcileError):
    # 口径对不齐即失败（绝不静默凑数）：返回 422 与具体不符项。
    return JSONResponse(status_code=422,
                        content={"code": "plan_reconcile_failed", "message": str(exc)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")
