from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger
from api.auth import require_api_key
from db.client import get_pool
from db.queries.opportunities import get_opportunity_by_id
from db.queries.leads import create_lead
from automation.llm_client import LLMClient

router = APIRouter()
_llm = LLMClient()


class GenerateRequest(BaseModel):
    opportunity_id: UUID
    contact_id: UUID | None = None
    generate_email: bool = False


class GenerateResponse(BaseModel):
    lead_id: UUID
    message: str
    email: str | None = None
    company_name: str
    score: int


@router.post("/generate/message", response_model=GenerateResponse, dependencies=[Depends(require_api_key)])
async def generate_message(body: GenerateRequest):
    """
    Récupère l'opportunité en DB, génère un message LinkedIn via LLM,
    sauvegarde le lead et retourne le message.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        opp = await get_opportunity_by_id(conn, body.opportunity_id)
        if not opp:
            raise HTTPException(status_code=404, detail=f"Opportunité {body.opportunity_id} introuvable")

        opp_dict = dict(opp)
        company_dict = {
            "name":    opp_dict.get("company_name", ""),
            "sector":  opp_dict.get("company_sector", ""),
            "country": opp_dict.get("country", "FR"),
        }

        logger.info(
            f"Génération message pour {company_dict['name']} | "
            f"tech={opp_dict.get('technologies')} | score={opp_dict.get('priority_score')}"
        )

        linkedin_msg = await _llm.generate_linkedin_message(opp_dict, company_dict)

        email_text = None
        if body.generate_email:
            email_text = await _llm.generate_email(opp_dict, company_dict)

        lead_id = await create_lead(
            conn,
            opportunity_id=body.opportunity_id,
            contact_id=body.contact_id,
            linkedin_msg=linkedin_msg,
            email_msg=email_text,
        )

        logger.success(f"Lead créé: {lead_id} | entreprise: {company_dict['name']}")

        return GenerateResponse(
            lead_id=lead_id,
            message=linkedin_msg,
            email=email_text,
            company_name=company_dict["name"],
            score=opp_dict.get("priority_score", 0),
        )


@router.get("/prospects", dependencies=[Depends(require_api_key)])
async def get_prospects(min_score: int = 0, country: str | None = None, limit: int = 20):
    """Retourne les meilleures opportunités filtrées par score et pays."""
    from db.queries.opportunities import get_top_opportunities
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await get_top_opportunities(conn, min_score=min_score, country=country, limit=limit)
    return [dict(r) for r in rows]
