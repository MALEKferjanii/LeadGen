from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from loguru import logger
from api.auth import require_api_key

router = APIRouter()


class CollectResponse(BaseModel):
    status: str
    message: str


async def _run_linkedin_b2b():
    """Signaux directs B2B : RFP, AO, sous-traitance, partenariat."""
    try:
        from collectors.linkedin_b2b import LinkedInB2BCollector
        from collectors.session_manager import SessionManager
        session = SessionManager()
        await session.initialize()
        client = session.get_client()
        collector = LinkedInB2BCollector(client=client)
        n = await collector.collect(dry_run=False)
        logger.success(f"LinkedIn B2B background collection done: {n} prospects")
    except Exception as e:
        logger.error(f"LinkedIn B2B background collection failed: {e}")


async def _run_linkedin():
    """Signaux indirects : offres d'emploi IT → outsourcing signal."""
    try:
        from collectors.linkedin_hiring import collect_hiring_signals
        from collectors.session_manager import SessionManager
        session = SessionManager()
        await session.initialize()
        client = session.get_client()
        n = await collect_hiring_signals(client, dry_run=False)
        logger.success(f"LinkedIn outsourcing signal collection done: {n} prospects")
    except Exception as e:
        logger.error(f"LinkedIn collection failed: {e}")


async def _run_all():
    try:
        from collectors.run_all import run_all
        n = await run_all(dry_run=False)
        logger.success(f"Full background collection done: {n} prospects total")
    except Exception as e:
        logger.error(f"Full background collection failed: {e}")


@router.post(
    "/collect/linkedin",
    response_model=CollectResponse,
    dependencies=[Depends(require_api_key)],
)
async def trigger_linkedin_collect(background_tasks: BackgroundTasks):
    """Déclenche les deux collecteurs LinkedIn (B2B direct + signal externalisation)."""
    background_tasks.add_task(_run_linkedin_b2b)
    background_tasks.add_task(_run_linkedin)
    return CollectResponse(
        status="started",
        message="Collecte LinkedIn démarrée : signaux B2B directs (RFP/AO/partenariat) + signaux externalisation",
    )


@router.post(
    "/collect/all",
    response_model=CollectResponse,
    dependencies=[Depends(require_api_key)],
)
async def trigger_full_collect(background_tasks: BackgroundTasks):
    """Déclenche la collecte complète (LinkedIn + BOAMP + TED + Malt) en arrière-plan."""
    background_tasks.add_task(_run_all)
    return CollectResponse(
        status="started",
        message="Collecte complète démarrée en arrière-plan (LinkedIn + BOAMP + TED + Malt)",
    )
