"""
Collecteur TwagoFreelance.com — Missions freelance IT Europe francophone.

Logique : plateforme freelance couvrant FR, BE, CH, LU — chaque mission publiée
signale un besoin IT confirmé avec budget disponible (b2b_subcontracting).

Source publique, pas d'authentification requise.
URL : https://www.twagofreelance.com
"""
import asyncio
import hashlib
import re
import json
from dataclasses import dataclass
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx

from collectors.base import BaseCollector

TWAGO_BASE_URL = "https://www.twagofreelance.com"
TWAGO_PROJECTS_URL = "https://www.twagofreelance.com/fr/projets-freelance"

# Catégories IT → (slug_url, technology, sector_hint, boost, country_iso)
TWAGO_SEARCHES = [
    ("informatique",            "Python",           "Tech",            12, "FR"),
    ("developpement-web",       "React",            "Tech/e-commerce",  8, "FR"),
    ("java",                    "Java",             "Finance/Banque",  10, "FR"),
    ("devops-cloud",            "DevOps",           "Tech",            10, "FR"),
    ("data-science",            "Machine Learning", "Tech/IA",         15, "FR"),
    ("erp-sap",                 "SAP",              "Industrie/RH",    12, "FR"),
    ("securite-informatique",   "DevOps",           "Tech",            10, "BE"),
    ("intelligence-artificielle","Machine Learning","Tech/IA",         15, "BE"),
    ("developpement-logiciel",  "Python",           "Tech",            12, "CH"),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://www.twagofreelance.com/",
}

COUNTRY_MAP = {"FR": "France", "BE": "Belgique", "CH": "Suisse", "LU": "Luxembourg"}


@dataclass
class TwagoMission:
    title: str
    company: str
    description: str
    budget: str
    technology: str
    sector_hint: str
    priority_boost: int
    country_iso: str
    url: str
    raw: dict


class TwagoCollector(BaseCollector):
    name = "twago"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _fetch(
        self, category: str, technology: str, sector: str, boost: int, country: str
    ) -> list[TwagoMission]:
        url = f"{TWAGO_PROJECTS_URL}/{category}"
        async with httpx.AsyncClient(
            timeout=25, headers=HEADERS, follow_redirects=True
        ) as client:
            r = await client.get(url)

        if r.status_code == 403:
            logger.warning(f"Twago — 403 sur '{category}'")
            return []
        if r.status_code == 404:
            # Essai avec l'URL de base + paramètre
            async with httpx.AsyncClient(
                timeout=25, headers=HEADERS, follow_redirects=True
            ) as client:
                r = await client.get(TWAGO_PROJECTS_URL, params={"q": technology})
            if r.status_code != 200:
                return []

        r.raise_for_status()
        return self._parse_html(r.text, technology, sector, boost, country)

    def _parse_html(
        self, html: str, technology: str, sector: str, boost: int, country: str
    ) -> list[TwagoMission]:
        missions: list[TwagoMission] = []

        # Recherche JSON embarqué (Symfony/PHP souvent injecte un objet JS)
        for pattern in [
            r'window\.__INITIAL_DATA__\s*=\s*({.*?});\s*</script>',
            r'var\s+pageData\s*=\s*({.*?});\s*</script>',
            r'<script[^>]+type="application/json"[^>]*>(.*?)</script>',
        ]:
            json_match = re.search(pattern, html, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    projects = (
                        data.get("projects", [])
                        or data.get("items", [])
                        or data.get("results", [])
                    )
                    for p in projects[:15]:
                        title = p.get("title", p.get("name", ""))
                        company = (
                            p.get("company", {}).get("name", "")
                            or p.get("client", {}).get("name", "")
                            or p.get("clientName", "")
                        )
                        desc = p.get("description", "")[:300]
                        budget = str(p.get("budget", p.get("price", "")))
                        url = p.get("url", p.get("link", TWAGO_PROJECTS_URL))
                        if not url.startswith("http"):
                            url = f"{TWAGO_BASE_URL}{url}"
                        if title:
                            missions.append(TwagoMission(
                                title=title[:150], company=company[:100] or "Client Twago",
                                description=desc, budget=budget, technology=technology,
                                sector_hint=sector, priority_boost=boost,
                                country_iso=country, url=url,
                                raw={"title": title, "company": company, "budget": budget},
                            ))
                    if missions:
                        return missions
                except (json.JSONDecodeError, KeyError):
                    pass

        # Fallback HTML — blocs projet courants en PHP/Twig
        blocks = re.findall(
            r'<(?:article|li|div)[^>]+class="[^"]*(?:project|mission|offer)[^"]*"[^>]*>'
            r'(.*?)</(?:article|li|div)>',
            html, re.DOTALL | re.IGNORECASE
        )
        for block in blocks[:20]:
            title_m = re.search(
                r'<(?:h[1-4]|strong)[^>]*>\s*<a[^>]*>([^<]{5,150})</a>', block
            )
            budget_m = re.search(r'(\d[\d\s]*€|\d+\s*euros)', block, re.IGNORECASE)
            link_m = re.search(r'href="(/[^"]*(?:projet|project|mission)[^"]*)"', block)
            company_m = re.search(
                r'(?:client|entreprise|société)[^>]*>\s*([A-ZÀ-Ü][^<]{2,60})<',
                block, re.IGNORECASE
            )

            if not title_m:
                continue

            title = title_m.group(1).strip()
            company = company_m.group(1).strip() if company_m else "Client Twago"
            budget = budget_m.group(1).strip() if budget_m else ""
            url = f"{TWAGO_BASE_URL}{link_m.group(1)}" if link_m else TWAGO_PROJECTS_URL

            missions.append(TwagoMission(
                title=title[:150], company=company[:100],
                description=f"Mission freelance IT — {technology}",
                budget=budget, technology=technology,
                sector_hint=sector, priority_boost=boost,
                country_iso=country, url=url,
                raw={"title": title, "company": company, "budget": budget},
            ))

        return missions

    async def collect(self, dry_run: bool = False) -> int:
        self.log_start()
        total = 0
        seen: set[str] = set()

        for category, technology, sector, boost, country in TWAGO_SEARCHES:
            try:
                missions = await self._fetch(category, technology, sector, boost, country)
                logger.info(f"Twago '{category}' ({country}): {len(missions)} missions")

                for m in missions:
                    key = hashlib.md5(f"{m.company}:{m.title}".encode()).hexdigest()
                    if key in seen or not m.company or m.company == "Client Twago":
                        continue
                    seen.add(key)

                    if dry_run:
                        logger.info(
                            f"[DRY RUN] Twago: {m.company} | {m.country_iso} | "
                            f"{m.technology} | {m.title[:60]} | budget: {m.budget}"
                        )
                        continue

                    from pipeline.ingest import ingest_raw_dict
                    slug = m.company.lower().replace(" ", "-")[:50]
                    ingested = await ingest_raw_dict({
                        "company_name": m.company,
                        "company_linkedin_url": f"https://twagofreelance.com/client/{slug}",
                        "company_universal_name": f"twago-{slug}",
                        "job_title": m.title,
                        "job_url": m.url,
                        "location": COUNTRY_MAP.get(m.country_iso, "France"),
                        "country_iso": m.country_iso,
                        "technology": m.technology,
                        "sector_hint": m.sector_hint,
                        "priority_boost": m.priority_boost,
                        "raw_job": m.raw,
                    }, source_platform="twago", opportunity_type="b2b_subcontracting")
                    if ingested:
                        total += 1
                        logger.success(
                            f"Twago ingéré: {m.company} | {m.country_iso} | {m.technology}"
                        )

            except Exception as e:
                logger.warning(f"Twago '{category}' failed: {e}")

            await asyncio.sleep(2.0)

        self.log_done(total)
        return total
