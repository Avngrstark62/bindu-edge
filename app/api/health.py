from fastapi import APIRouter

router = APIRouter()


@router.get("/health/live")
async def liveness():
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness():
    # Phase 0: always ready
    # Later: check Redis, CP, etc.
    return {"status": "ready"}
