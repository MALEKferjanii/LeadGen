from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from loguru import logger
from api.auth import require_api_key
from db.client import get_pool
from db.queries.opportunities import update_nlp_labels, get_opportunity_by_id
from nlp.scorer import compute_nlp_score

router = APIRouter()

# Le classificateur est initialisé dans main.py et attaché à app.state
_clf = None


def get_clf():
    return _clf


class ClassifyRequest(BaseModel):
    text: str
    opportunity_id: UUID | None = None


class ClassifyResponse(BaseModel):
    sector_label: str
    sector_confidence: float
    tech_label: str
    tech_confidence: float
    priority_label: str
    priority_confidence: float
    nlp_score: int


@router.post("/classify", response_model=ClassifyResponse, dependencies=[Depends(require_api_key)])
async def classify_text(body: ClassifyRequest):
    """
    Classifie un texte IT. Si opportunity_id fourni, met à jour les labels en DB.
    """
    from api.main import app
    clf = getattr(app.state, "classifier", None)
    if not clf or not clf.is_ready():
        raise HTTPException(status_code=503, detail="Modèle NLP non chargé. Lancez `make train` d'abord.")

    prediction = clf.predict(body.text)
    logger.info(
        f"Classification: secteur={prediction['sector_label']} | "
        f"tech={prediction['tech_label']} | priorité={prediction['priority_label']}"
    )

    if body.opportunity_id:
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                opp = await get_opportunity_by_id(conn, body.opportunity_id)
                if opp:
                    rule_score = opp["priority_score"] or 50
                    nlp_score  = compute_nlp_score(rule_score, prediction)
                    await update_nlp_labels(
                        conn,
                        body.opportunity_id,
                        prediction["sector_label"],
                        prediction["tech_label"],
                        prediction["priority_label"],
                        prediction["priority_confidence"],
                        nlp_score,
                    )
                    logger.info(f"Labels NLP mis à jour pour opportunité {body.opportunity_id}")
        except Exception as e:
            logger.error(f"Mise à jour DB échouée: {e}")

    nlp_score = compute_nlp_score(50, prediction)
    return ClassifyResponse(**prediction, nlp_score=nlp_score)
