"""
Enrichissement email via Hunter.io.
Appelé sur les contacts détecteurs à haut score (>= 70) pour compléter l'email.
"""
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from config.settings import get_settings

settings = get_settings()

HUNTER_DOMAIN_SEARCH_URL = "https://api.hunter.io/v2/domain-search"
HUNTER_EMAIL_VERIFIER_URL = "https://api.hunter.io/v2/email-verifier"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
async def find_email(domain: str, full_name: str) -> str | None:
    """
    Tente de trouver l'email d'un contact via Hunter.io.
    Retourne l'email trouvé ou None si introuvable / pas de clé API.
    """
    if not settings.hunter_api_key:
        logger.debug("Hunter.io non configuré — enrichissement email ignoré")
        return None

    first_name, *last_parts = full_name.split(" ", 1)
    last_name = last_parts[0] if last_parts else ""

    params = {
        "domain": domain,
        "first_name": first_name,
        "last_name": last_name,
        "api_key": settings.hunter_api_key,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(HUNTER_DOMAIN_SEARCH_URL, params=params)
            r.raise_for_status()
            data = r.json().get("data", {})
            emails = data.get("emails", [])
            if emails:
                email = emails[0].get("value")
                logger.info(f"Email trouvé via Hunter.io: {email} pour {full_name} @ {domain}")
                return email
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.warning("Hunter.io rate limit atteint")
                raise
            logger.warning(f"Hunter.io error {e.response.status_code}: {e}")
    return None


async def enrich_contact(company_domain: str, contact_name: str) -> dict:
    """Retourne un dict avec l'email enrichi (ou vide si non trouvé)."""
    email = await find_email(company_domain, contact_name)
    return {"email": email, "enriched": email is not None}
