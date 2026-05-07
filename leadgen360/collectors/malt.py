"""
Collecteur Malt.fr — Missions freelance comme signal de besoin IT.

Logique : une entreprise qui publie une mission freelance = besoin confirmé,
souvent urgent (deadline courte, budget disponible maintenant).

Malt est une SPA React mais expose un endpoint JSON non-documenté
utilisé par son propre front. On parse directement ce JSON.
"""
import asyncio
import hashlib
from dataclasses import dataclass
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx

from collectors.base import BaseCollector

MALT_API_URL = "https://www.malt.fr/api/1/search/project-suggestions"

MALT_QUERIES = [
    ("COBOL",            "Finance/Banque",     25),
    ("Java",             "Finance/Assurance",  10),
    ("Python",           "Tech/IA",            15),
    ("DevOps",           "Tech",               10),
    ("SAP",              "Industrie/RH",       12),
    ("Salesforce",       "CRM/Retail",         8),
    ("Data Engineer",    "Tech/IA",            12),
    ("Machine Learning", "Tech/IA",            15),
    ("React",            "Tech/e-commerce",    5),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fr-FR,fr;q=0.9",
    "Referer": "https://www.malt.fr/s",
    "Origin": "https://www.malt.fr",
}


@dataclass
class MaltMission:
    title: str
    company: str
    location: str
    technology: str
    sector_hint: str
    priority_boost: int
    url: str
    raw: dict


class MaltCollector(BaseCollector):
    name = "malt"

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=3, max=15))
    async def _search(self, query: str, sector: str, boost: int) -> list[MaltMission]:
        params = {
            "query": query,
            "page": 0,
            "size": 20,
            "projectType": "PROJECT",
        }
        try:
            async with httpx.AsyncClient(
                timeout=20, headers=HEADERS, follow_redirects=True
            ) as client:
                r = await client.get(MALT_API_URL, params=params)

            if r.status_code == 404 or r.status_code == 403:
                # Malt blocked or endpoint changed — try HTML fallback
                return await self._search_html_fallback(query, sector, boost)

            r.raise_for_status()
            data = r.json()

        except (httpx.HTTPStatusError, httpx.ConnectError, ValueError):
            return await self._search_html_fallback(query, sector, boost)

        missions = []
        items = data.get("hits", data.get("results", data.get("content", [])))
        for item in items:
            title = item.get("title", item.get("name", ""))
            company = (
                item.get("company", {}).get("name", "")
                or item.get("clientName", "")
                or item.get("organizationName", "")
            )
            location = item.get("location", item.get("city", "France"))
            slug = item.get("slug", item.get("id", ""))
            url = f"https://www.malt.fr/project/{slug}" if slug else "https://www.malt.fr"

            if not title or not company:
                continue

            missions.append(MaltMission(
                title=title[:150],
                company=company[:100],
                location=location,
                technology=query,
                sector_hint=sector,
                priority_boost=boost,
                url=url,
                raw={"title": title, "company": company, "location": location},
            ))

        return missions

    async def _search_html_fallback(
        self, query: str, sector: str, boost: int
    ) -> list[MaltMission]:
        """
        Fallback HTML scraping via Malt search page.
        Malt renders server-side JSON in a __NEXT_DATA__ script tag.
        """
        try:
            async with httpx.AsyncClient(
                timeout=25, headers=HEADERS, follow_redirects=True
            ) as client:
                r = await client.get(
                    "https://www.malt.fr/s",
                    params={"q": query, "type": "project"},
                )

            import re, json
            match = re.search(
                r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
                r.text,
                re.DOTALL,
            )
            if not match:
                return []

            next_data = json.loads(match.group(1))
            items = (
                next_data.get("props", {})
                .get("pageProps", {})
                .get("searchResults", {})
                .get("hits", [])
            )

            missions = []
            for item in items[:10]:
                title = item.get("title", "")
                company = item.get("company", {}).get("name", "") or item.get("clientName", "")
                if not title:
                    continue
                slug = item.get("slug", "")
                missions.append(MaltMission(
                    title=title[:150],
                    company=company[:100] or "Entreprise Malt",
                    location=item.get("city", "France"),
                    technology=query,
                    sector_hint=sector,
                    priority_boost=boost,
                    url=f"https://www.malt.fr/project/{slug}" if slug else "https://www.malt.fr",
                    raw={"title": title, "company": company},
                ))
            return missions

        except Exception as e:
            logger.debug(f"Malt HTML fallback failed for '{query}': {e}")
            return []

    async def collect(self, dry_run: bool = False) -> int:
        self.log_start()
        total = 0
        seen: set[str] = set()

        for query, sector, boost in MALT_QUERIES:
            try:
                missions = await self._search(query, sector, boost)
                logger.info(f"Malt '{query}': {len(missions)} missions trouvées")

                for m in missions:
                    key = hashlib.md5(f"{m.company}:{m.technology}".encode()).hexdigest()
                    if key in seen or not m.company:
                        continue
                    seen.add(key)

                    if dry_run:
                        logger.info(
                            f"[DRY RUN] Malt: {m.company} | "
                            f"{m.technology} | {m.title[:60]}"
                        )
                        continue

                    from pipeline.ingest import ingest_raw_dict
                    slug = m.company.lower().replace(" ", "-")[:50]
                    ingested = await ingest_raw_dict({
                        "company_name": m.company,
                        "company_linkedin_url": f"https://malt.fr/client/{slug}",
                        "company_universal_name": f"malt-{slug}",
                        "job_title": m.title,
                        "job_url": m.url,
                        "location": m.location,
                        "country_iso": "FR",
                        "technology": m.technology,
                        "sector_hint": m.sector_hint,
                        "priority_boost": m.priority_boost,
                        "raw_job": m.raw,
                    }, source_platform="malt")
                    if ingested:
                        total += 1
                        logger.success(f"Malt ingéré: {m.company} | {m.technology}")

            except Exception as e:
                logger.warning(f"Malt '{query}' failed: {e}")

            await asyncio.sleep(2.5)

        self.log_done(total)
        return total
