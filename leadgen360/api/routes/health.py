from fastapi import APIRouter
from db.client import get_pool
from loguru import logger

router = APIRouter()


@router.get("/health")
async def health():
    """Healthcheck utilisé par Docker et n8n pour vérifier la disponibilité de l'API."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "ok"
    except Exception as e:
        logger.warning(f"DB healthcheck failed: {e}")
        db_status = "error"

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "service": "leadgen360-api",
        "version": "1.0.0",
    }
