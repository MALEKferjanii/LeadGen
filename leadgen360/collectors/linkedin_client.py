"""
Wrapper autour de linkedin-api (unofficial).
Utilise les endpoints mobiles internes de LinkedIn — bien plus discrets que Selenium.
Les cookies sont persistés sur disque pour éviter les re-authentifications répétées.
"""
import asyncio
from pathlib import Path
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
from config.settings import get_settings

settings = get_settings()


class LinkedInClient:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self._api = None
        self._loop = None

    def _get_loop(self):
        try:
            return asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.new_event_loop()

    async def connect(self) -> bool:
        Path(settings.cookies_dir).mkdir(parents=True, exist_ok=True)
        loop = self._get_loop()
        try:
            from linkedin_api import Linkedin
            self._api = await loop.run_in_executor(
                None,
                lambda: Linkedin(
                    self.email,
                    self.password,
                    cookies_dir=settings.cookies_dir,
                    authenticate=True,
                    refresh_cookies=False,
                )
            )
            logger.info(f"LinkedIn session ready: {self.email}")
            return True
        except Exception as e:
            err = str(e).upper()
            if "CHALLENGE" in err:
                logger.critical(
                    f"CHALLENGE_REQUIRED pour {self.email}. "
                    "Connectez-vous manuellement sur linkedin.com pour réinitialiser la session."
                )
            elif "RESTRICTED" in err or "BLOCKED" in err:
                logger.error(f"Compte {self.email} restreint par LinkedIn: {e}")
            else:
                logger.error(f"Échec authentification LinkedIn {self.email}: {e}")
            return False

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def _run(self, fn):
        loop = self._get_loop()
        return await loop.run_in_executor(None, fn)

    async def search_jobs(self, keywords: str, location: str, limit: int = 50) -> list[dict]:
        if not self._api:
            raise RuntimeError("Non connecté. Appelez connect() d'abord.")
        try:
            results = await self._run(
                lambda: self._api.search_jobs(
                    keywords=keywords,
                    location_name=location,
                    limit=limit,
                )
            )
            return results or []
        except Exception as e:
            logger.warning(f"search_jobs({keywords!r}, {location!r}): {e}")
            return []

    async def search_companies(self, keywords: str, limit: int = 25) -> list[dict]:
        if not self._api:
            raise RuntimeError("Non connecté.")
        try:
            results = await self._run(
                lambda: self._api.search_companies(keywords=keywords, limit=limit)
            )
            return results or []
        except Exception as e:
            logger.warning(f"search_companies({keywords!r}): {e}")
            return []

    async def get_company(self, universal_name: str) -> Optional[dict]:
        if not self._api:
            raise RuntimeError("Non connecté.")
        try:
            return await self._run(lambda: self._api.get_company(universal_name))
        except Exception as e:
            logger.warning(f"get_company({universal_name!r}): {e}")
            return None

    async def get_job(self, job_id: str) -> Optional[dict]:
        if not self._api:
            raise RuntimeError("Non connecté.")
        try:
            return await self._run(lambda: self._api.get_job(job_id))
        except Exception as e:
            logger.warning(f"get_job({job_id!r}): {e}")
            return None

    async def get_profile(self, public_id: str) -> Optional[dict]:
        if not self._api:
            raise RuntimeError("Non connecté.")
        try:
            return await self._run(lambda: self._api.get_profile(public_id))
        except Exception as e:
            logger.warning(f"get_profile({public_id!r}): {e}")
            return None

    async def search_content(self, keywords: str, limit: int = 20) -> list[dict]:
        """Search LinkedIn posts/content by keywords (B2B signals)."""
        if not self._api:
            raise RuntimeError("Non connecté.")
        try:
            results = await self._run(
                lambda: self._api.search(
                    {
                        "keywords": keywords,
                        "filters": "List((filter:resultType,values:List(CONTENT)))",
                    },
                    limit=limit,
                )
            )
            return results or []
        except Exception as e:
            logger.warning(f"search_content({keywords!r}): {e}")
            return []

    async def get_company_updates_by_id(self, urn_id: str, max_results: int = 10) -> list[dict]:
        """Get recent posts from a company page using numeric URN ID."""
        if not self._api:
            raise RuntimeError("Non connecté.")
        try:
            return await self._run(
                lambda: self._api.get_company_updates(
                    urn_id=urn_id, max_results=max_results
                )
            )
        except Exception as e:
            logger.warning(f"get_company_updates_by_id({urn_id!r}): {e}")
            return []

    async def get_company_updates(self, universal_name: str, max_results: int = 10) -> list[dict]:
        """Get recent posts from a company page using public slug name."""
        if not self._api:
            raise RuntimeError("Non connecté.")
        try:
            return await self._run(
                lambda: self._api.get_company_updates(
                    public_id=universal_name, max_results=max_results
                )
            )
        except Exception as e:
            logger.warning(f"get_company_updates({universal_name!r}): {e}")
            return []
