from fastapi import APIRouter, Depends
from pydantic import BaseModel
from loguru import logger
from api.auth import require_api_key
from pipeline.ingest import ingest_raw_dict

router = APIRouter()


class IngestRequest(BaseModel):
    prospects: list[dict]


class IngestResponse(BaseModel):
    ingested: int
    duplicates: int
    errors: int


@router.post("/ingest", response_model=IngestResponse, dependencies=[Depends(require_api_key)])
async def ingest_prospects(body: IngestRequest):
    """
    Appelé par les webhooks n8n après chaque batch de scraping.
    Insère les prospects dans la DB après déduplication.
    """
    ingested = duplicates = errors = 0

    for raw in body.prospects:
        try:
            new = await ingest_raw_dict(raw)
            if new:
                ingested += 1
            else:
                duplicates += 1
        except Exception as e:
            logger.error(f"Ingest error for prospect {raw.get('company_name')}: {e}")
            errors += 1

    logger.info(f"Batch ingest: {ingested} nouveaux, {duplicates} doublons, {errors} erreurs")
    return IngestResponse(ingested=ingested, duplicates=duplicates, errors=errors)
