from fastapi import APIRouter
from app.api import absentees, candidates, halls, papers, seating
api_router = APIRouter()

@api_router.get("/health")
def health():
    return {"status": "ok"}

api_router.include_router(halls.router)
api_router.include_router(candidates.router)
api_router.include_router(papers.router)
api_router.include_router(absentees.router)
api_router.include_router(seating.router)
