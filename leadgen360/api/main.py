"""
LeadGen Francophone 360+ — FastAPI Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger

from db.client import get_pool, close_pool
from api.routes import health, ingest, classify, generate, collect


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ─── Startup ────────────────────────────────────────────────────────────
    logger.info("Démarrage de l'API LeadGen 360+")

    # Connexion DB
    try:
        await get_pool()
        logger.success("Pool asyncpg connecté")
    except Exception as e:
        logger.error(f"Impossible de se connecter à PostgreSQL: {e}")

    # Chargement du modèle NLP (si disponible)
    try:
        from nlp.classifier import OpportunityClassifier
        clf = OpportunityClassifier()
        clf.load()
        app.state.classifier = clf
        logger.success("Modèle NLP chargé")
    except Exception as e:
        logger.warning(f"Modèle NLP non disponible: {e}. Lancez 'make train'.")
        app.state.classifier = None

    yield

    # ─── Shutdown ────────────────────────────────────────────────────────────
    await close_pool()
    logger.info("API arrêtée proprement")


app = FastAPI(
    title="LeadGen Francophone 360+ API",
    description="Plateforme de génération de leads B2B IT pour Solvinya Group",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router, tags=["Santé"])
app.include_router(ingest.router, prefix="/api", tags=["Ingestion"])
app.include_router(classify.router, prefix="/api", tags=["Classification NLP"])
app.include_router(generate.router, prefix="/api", tags=["Génération LLM"])
app.include_router(collect.router, prefix="/api", tags=["Collecte"])


@app.get("/")
async def root():
    return {
        "service": "LeadGen Francophone 360+",
        "docs": "/docs",
        "health": "/health",
    }
