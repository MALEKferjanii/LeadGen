"""
Collecteur TED (Tenders Electronic Daily) — Marchés publics IT de l'UE.
Source pour FR, BE, LU, CH : les organisations qui lancent des appels
d'offres IT sont des prospects B2B pour Solvinya (intégration, dev, infra).

API officielle gratuite : https://api.ted.europa.eu/v3/notices/search
Syntaxe expert : https://ted.europa.eu/en/help/expert-search
"""
import asyncio
from dataclasses import dataclass
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx

from collectors.base import BaseCollector

TED_API_URL = "https://api.ted.europa.eu/v3/notices/search"

TED_FIELDS = [
    "notice-title",
    "buyer-name",
    "publication-date",
    "notice-type",
    "classification-cpv",
    "buyer-country",
    "publication-number",
    "announcement-url",
]

# CPV 72xxx = services informatiques
IT_CPV_PREFIXES = ["72", "48"]

# Mots-clés IT dans les titres (requêtes par pays)
IT_TITLE_KEYWORDS = [
    "informatique",
    "logiciel",
    "développement",
    "système d'information",
    "infrastructure",
    "cybersécurité",
    "cloud",
    "ERP",
    "SAP",
    "COBOL",
    "data",
    "intelligence artificielle",
    "DevOps",
    "intégration",
]

COUNTRY_CONFIG = {
    "FRA": ("FR", "France"),
    "BEL": ("BE", "Belgique"),
    "LUX": ("LU", "Luxembourg"),
    "CHE": ("CH", "Suisse"),
}

SECTOR_BY_CPV_PREFIX = {
    "72": ("Tech", 10),
    "48": ("Tech", 8),
}

BOOST_BY_KEYWORD = {
    "COBOL": 25,
    "SAP": 12,
    "cybersécurité": 12,
    "intelligence artificielle": 15,
    "ERP": 10,
    "développement": 8,
    "logiciel": 8,
    "informatique": 6,
    "data": 10,
    "cloud": 8,
    "DevOps": 10,
    "infrastructure": 8,
    "intégration": 8,
    "système d'information": 8,
}


@dataclass
class TedNotice:
    publication_number: str
    title_fr: str
    buyer_name: str
    country_iso2: str
    country_label: str
    publication_date: str
    notice_type: str
    cpv_codes: list[str]
    technology: str
    sector_hint: str
    priority_boost: int
    url: str
    raw: dict


class TedCollector(BaseCollector):
    name = "ted"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    async def _search(
        self, country_code: str, keyword: str, limit: int = 20
    ) -> list[TedNotice]:
        iso2, country_label = COUNTRY_CONFIG[country_code]
        boost = BOOST_BY_KEYWORD.get(keyword, 6)

        query = f'notice-title="{keyword}" AND buyer-country={country_code}'
        payload = {
            "query": query,
            "fields": TED_FIELDS,
            "limit": limit,
        }
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.post(TED_API_URL, json=payload)
            r.raise_for_status()

        data = r.json()
        notices = []
        for item in data.get("notices", []):
            pub_num = item.get("publication-number", "")

            title_dict = item.get("notice-title", {})
            title_fr = (
                title_dict.get("fra")
                or title_dict.get("eng")
                or next(iter(title_dict.values()), "")
            )
            if isinstance(title_fr, list):
                title_fr = title_fr[0] if title_fr else ""

            buyer_dict = item.get("buyer-name", {})
            buyer_name = (
                buyer_dict.get("fra")
                or buyer_dict.get("eng")
                or next(iter(buyer_dict.values()), [""])[0]
            )
            if isinstance(buyer_name, list):
                buyer_name = buyer_name[0] if buyer_name else ""

            cpv_codes = item.get("classification-cpv", [])
            pub_date = item.get("publication-date", "")
            notice_type = item.get("notice-type", "")

            sector_hint = "Tech"
            for cpv in cpv_codes:
                for prefix, (sector, _) in SECTOR_BY_CPV_PREFIX.items():
                    if cpv.startswith(prefix):
                        sector_hint = sector
                        break

            url = f"https://ted.europa.eu/en/notice/-/detail/{pub_num}"
            if not title_fr or not buyer_name:
                continue

            notices.append(TedNotice(
                publication_number=pub_num,
                title_fr=str(title_fr)[:200],
                buyer_name=str(buyer_name)[:100],
                country_iso2=iso2,
                country_label=country_label,
                publication_date=pub_date,
                notice_type=notice_type,
                cpv_codes=cpv_codes,
                technology=keyword,
                sector_hint=sector_hint,
                priority_boost=boost,
                url=url,
                raw={
                    "publication_number": pub_num,
                    "title": str(title_fr)[:200],
                    "buyer": str(buyer_name)[:100],
                    "cpv": cpv_codes,
                    "date": pub_date,
                },
            ))

        return notices

    async def _fetch_all(self) -> list[TedNotice]:
        all_notices: list[TedNotice] = []
        seen: set[str] = set()

        for country_code in COUNTRY_CONFIG:
            for keyword in IT_TITLE_KEYWORDS:
                try:
                    notices = await self._search(country_code, keyword, limit=15)
                    for n in notices:
                        key = f"{n.buyer_name}:{n.technology}:{n.country_iso2}"
                        if key not in seen:
                            seen.add(key)
                            all_notices.append(n)
                    if notices:
                        logger.info(
                            f"TED '{keyword}' [{country_code}]: {len(notices)} appels d'offres"
                        )
                    await asyncio.sleep(0.3)
                except Exception as e:
                    logger.warning(f"TED '{keyword}' [{country_code}] failed: {e}")

        logger.info(f"TED total: {len(all_notices)} appels d'offres IT")
        return all_notices

    async def collect(self, dry_run: bool = False) -> int:
        self.log_start()
        try:
            notices = await self._fetch_all()
            if not notices:
                logger.warning("TED: aucun appel d'offres IT trouvé")
                return 0

            if dry_run:
                for n in notices:
                    logger.info(
                        f"[DRY RUN] TED: {n.buyer_name} [{n.country_iso2}] | "
                        f"{n.technology} | {n.title_fr[:60]}"
                    )
                return 0

            from pipeline.ingest import ingest_raw_dict
            count = 0
            for n in notices:
                slug = n.buyer_name.lower().replace(" ", "-").replace(",", "")[:50]
                ingested = await ingest_raw_dict({
                    "company_name": n.buyer_name,
                    "company_linkedin_url": f"https://ted.europa.eu/acheteur/{slug}",
                    "company_universal_name": f"ted-{slug}",
                    "job_title": n.title_fr[:120],
                    "job_url": n.url,
                    "location": n.country_label,
                    "country_iso": n.country_iso2,
                    "technology": n.technology,
                    "sector_hint": n.sector_hint,
                    "priority_boost": n.priority_boost,
                    "raw_job": n.raw,
                    "opportunity_type": "b2b_tender",
                }, source_platform="ted")
                if ingested:
                    count += 1
                    logger.success(
                        f"TED ingéré: {n.buyer_name} [{n.country_iso2}] | {n.technology}"
                    )
                await asyncio.sleep(0.1)

            self.log_done(count)
            return count

        except Exception as e:
            logger.error(f"TED collection failed: {e}")
            return 0
