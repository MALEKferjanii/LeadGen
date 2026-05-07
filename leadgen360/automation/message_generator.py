"""
Génération de messages LinkedIn personnalisés via LLM.
"""
from loguru import logger
from automation.llm_client import LLMClient

_client = LLMClient()


async def generate_linkedin_message(opportunity: dict, company: dict) -> str:
    logger.info(
        f"Génération message LinkedIn pour {company.get('name')} | "
        f"tech={opportunity.get('technologies')}"
    )
    msg = await _client.generate_linkedin_message(opportunity, company)
    logger.success(f"Message généré ({len(msg)} chars)")
    return msg
