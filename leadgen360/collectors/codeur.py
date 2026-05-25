"""
Collecteur Codeur.com — Missions freelance IT francophones.

Logique : une entreprise qui publie une mission freelance sur Codeur.com
a un besoin IT confirmé avec budget disponible. Signal de type b2b_subcontracting.

Source publique, pas d'authentification requise.
URL : https://www.codeur.com/projets
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

CODEUR_BASE_URL = "https://www.codeur.com"
CODEUR_PROJECTS_URL = "https://www.codeur.com/projets"

# Catégories IT sur Codeur.com → (slug, technology, sector_hint, boost)
CODEUR_CATEGORIES = [
    ("dev-logiciel",             "Python",           "Tech",           12),
    ("dev-web",                  "React",            "Tech/e-commerce", 8),
    ("reseau-systemes-securite", "DevOps",           "Tech",           10),
    ("dev-mobile",               "React",            "Tech",            7),
    ("erp-crm",                  "SAP",              "Industrie/RH",   12),
    ("intelligence-artificielle","Machine Learning", "Tech/IA",        15),
    ("big-data",                 "Data Engineer",    "Tech/IA",        12),
    ("java",                     "Java",             "Finance/Banque", 10),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://www.codeur.com/",
}


@dataclass
class CodeurMission:
    title: str
    company: str
    description: str
    budget: str
    technology: str
    sector_hint: str
    priority_boost: int
    url: str
    raw: dict


class CodeurCollector(BaseCollector):
    name = "codeur"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
    async def _fetch_category(
        self, category: str, technology: str, sector: str, boost: int
    ) -> list[CodeurMission]:
        params = {"category": category, "page": 1}
        async with httpx.AsyncClient(
            timeout=25, headers=HEADERS, follow_redirects=True
        ) as client:
            r = await client.get(CODEUR_PROJECTS_URL, params=params)

        if r.status_code == 403:
            logger.warning(f"Codeur.com — 403 sur catégorie '{category}'")
            return []

        r.raise_for_status()
        return self._parse_html(r.text, technology, sector, boost)

    def _parse_html(
        self, html: str, technology: str, sector: str, boost: int
    ) -> list[CodeurMission]:
        missions: list[CodeurMission] = []

        # Recherche du JSON embarqué (Nuxt / Next / Rails UJS)
        json_match = re.search(
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});\s*</script>',
            html, re.DOTALL
        )
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                projects = (
                    data.get("projects", {}).get("list", [])
                    or data.get("projects", [])
                )
                for p in projects:
                    title = p.get("title", p.get("name", ""))
                    company = p.get("user", {}).get("company", "") or p.get("author", "")
                    desc = p.get("description", p.get("short_description", ""))[:300]
                    budget = str(p.get("budget", p.get("price", "")))
                    slug = p.get("slug", p.get("id", ""))
                    url = f"{CODEUR_BASE_URL}/projets/{slug}" if slug else CODEUR_PROJECTS_URL
                    if title:
                        missions.append(CodeurMission(
                            title=title[:150], company=company[:100] or "Client Codeur",
                            description=desc, budget=budget, technology=technology,
                            sector_hint=sector, priority_boost=boost, url=url,
                            raw={"title": title, "company": company, "budget": budget},
                        ))
                return missions
            except (json.JSONDecodeError, KeyError):
                pass

        # Fallback : parsing HTML par regex sur les blocs projet
        # Codeur.com utilise des articles avec classe "project-card" ou similaire
        blocks = re.findall(
            r'<(?:article|div)[^>]+class="[^"]*project[^"]*"[^>]*>(.*?)</(?:article|div)>',
            html, re.DOTALL | re.IGNORECASE
        )
        for block in blocks[:20]:
            title_m = re.search(r'<h[23][^>]*>\s*<a[^>]*>([^<]{5,150})</a>', block)
            company_m = re.search(
                r'(?:client|entreprise|auteur)[^>]*>\s*([A-ZÀ-Ü][^<]{2,60})<', block,
                re.IGNORECASE
            )
            budget_m = re.search(r'(\d[\d\s]*€|\d+\s*euros)', block, re.IGNORECASE)
            link_m = re.search(r'href="(/projets/[^"]+)"', block)

            if not title_m:
                continue

            title = title_m.group(1).strip()
            company = company_m.group(1).strip() if company_m else "Client Codeur"
            budget = budget_m.group(1).strip() if budget_m else ""
            url = f"{CODEUR_BASE_URL}{link_m.group(1)}" if link_m else CODEUR_PROJECTS_URL

            missions.append(CodeurMission(
                title=title[:150], company=company[:100],
                description=f"Mission freelance IT — {technology}",
                budget=budget, technology=technology,
                sector_hint=sector, priority_boost=boost, url=url,
                raw={"title": title, "company": company, "budget": budget},
            ))

        return missions

    async def collect(self, dry_run: bool = False) -> int:
        self.log_start()
        total = 0
        seen: set[str] = set()

        for category, technology, sector, boost in CODEUR_CATEGORIES:
            try:
                missions = await self._fetch_category(category, technology, sector, boost)
                logger.info(f"Codeur '{category}': {len(missions)} missions")

                for m in missions:
                    key = hashlib.md5(f"{m.company}:{m.title}".encode()).hexdigest()
                    if key in seen or not m.company or m.company == "Client Codeur":
                        continue
                    seen.add(key)

                    if dry_run:
                        logger.info(
                            f"[DRY RUN] Codeur: {m.company} | "
                            f"{m.technology} | {m.title[:60]} | budget: {m.budget}"
                        )
                        continue

                    from pipeline.ingest import ingest_raw_dict
                    slug = m.company.lower().replace(" ", "-")[:50]
                    ingested = await ingest_raw_dict({
                        "company_name": m.company,
                        "company_linkedin_url": f"https://codeur.com/client/{slug}",
                        "company_universal_name": f"codeur-{slug}",
                        "job_title": m.title,
                        "job_url": m.url,
                        "location": "France",
                        "country_iso": "FR",
                        "technology": m.technology,
                        "sector_hint": m.sector_hint,
                        "priority_boost": m.priority_boost,
                        "raw_job": m.raw,
                    }, source_platform="codeur", opportunity_type="b2b_subcontracting")
                    if ingested:
                        total += 1
                        logger.success(f"Codeur ingéré: {m.company} | {m.technology}")

            except Exception as e:
                logger.warning(f"Codeur '{category}' failed: {e}")

            await asyncio.sleep(2.0)

        self.log_done(total)
        return total
