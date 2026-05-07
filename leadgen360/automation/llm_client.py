"""
Client LLM avec fallback automatique : Groq (rapide, gratuit) → Ollama (local).
"""
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger
from config.settings import get_settings

settings = get_settings()

LINKEDIN_MESSAGE_PROMPT = """\
Tu es un business developer senior chez Solvinya Group, une ESN spécialisée en IA et développement logiciel.

Rédige un message LinkedIn de prospection en français pour ce prospect :
- Entreprise : {company_name}
- Secteur : {sector}
- Technologie détectée : {technology}
- Pays : {country}
- Signal : cette entreprise recrute activement des profils {technology}

Règles strictes :
- Maximum 5 lignes
- Ton professionnel mais direct, pas vendeur
- Mentionner le signal spécifique (recrutement {technology})
- Terminer par une question ouverte sur leur projet
- NE PAS utiliser de formules génériques type "j'espère que vous allez bien"

Message :"""

EMAIL_PROMPT = """\
Tu es business developer senior chez Solvinya Group, ESN spécialisée IA et développement.

Rédige un email de prospection B2B en français :
- Destinataire : {contact_name} ({job_title})
- Entreprise : {company_name}, secteur {sector}
- Signal détecté : recrutement {technology}

Format :
- Objet accrocheur (1 ligne)
- Corps court (4-5 lignes max)
- Une question de qualification finale

Email complet :"""


class LLMClient:
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10))
    async def _groq(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                json={
                    "model": settings.groq_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 350,
                    "temperature": 0.7,
                },
            )
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"].strip()

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=3, max=15))
    async def _ollama(self, prompt: str) -> str:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            r.raise_for_status()
            return r.json()["response"].strip()

    async def generate(self, prompt: str) -> str:
        if settings.groq_api_key:
            try:
                return await self._groq(prompt)
            except Exception as e:
                logger.warning(f"Groq indisponible: {e} — fallback Ollama")
        return await self._ollama(prompt)

    async def generate_linkedin_message(self, opportunity: dict, company: dict) -> str:
        techs = opportunity.get("technologies") or ["IT"]
        tech  = techs[0] if isinstance(techs, list) else str(techs)
        prompt = LINKEDIN_MESSAGE_PROMPT.format(
            company_name=company.get("name", "cette entreprise"),
            sector=opportunity.get("sector_label") or company.get("sector", "IT"),
            technology=tech,
            country=opportunity.get("country", "FR"),
        )
        return await self.generate(prompt)

    async def generate_email(
        self,
        opportunity: dict,
        company: dict,
        contact_name: str = "Madame, Monsieur",
        job_title: str = "Responsable IT",
    ) -> str:
        techs = opportunity.get("technologies") or ["IT"]
        tech  = techs[0] if isinstance(techs, list) else str(techs)
        prompt = EMAIL_PROMPT.format(
            contact_name=contact_name,
            job_title=job_title,
            company_name=company.get("name", "votre entreprise"),
            sector=opportunity.get("sector_label") or company.get("sector", "IT"),
            technology=tech,
        )
        return await self.generate(prompt)
