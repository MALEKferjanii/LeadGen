"""
Génération d'emails de prospection personnalisés via LLM.
"""
from loguru import logger
from automation.llm_client import LLMClient

_client = LLMClient()


async def generate_email(
    opportunity: dict,
    company: dict,
    contact_name: str = "Madame, Monsieur",
    job_title: str = "Responsable IT",
) -> str:
    logger.info(f"Génération email pour {company.get('name')} → {contact_name}")
    email = await _client.generate_email(opportunity, company, contact_name, job_title)
    logger.success(f"Email généré ({len(email)} chars)")
    return email
