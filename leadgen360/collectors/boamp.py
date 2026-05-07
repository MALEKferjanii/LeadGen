"""
Collecteur BOAMP — Bulletin Officiel des Annonces de Marchés Publics.
Source secondaire pour les appels d'offres IT secteur public français.

Logique : un appel d'offres public IT = budget confirmé + acheteur identifié.
L'API BOAMP est publique et gratuite (flux RSS + API JSON officielle).
"""
import asyncio
from dataclasses import dataclass
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
import httpx

from collectors.base import BaseCollector

BOAMP_API_URL = "https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records"

TECH_KEYWORDS = {
    "SAP":               ("Industrie/RH",      12),
    "COBOL":             ("Finance/Banque",     25),
    "Java":              ("Finance/Assurance",  10),
    "Python":            ("Tech/IA",            15),
    "DevOps":            ("Tech",               10),
    "cloud":             ("Tech",               8),
    "cybersécurité":     ("Sécurité",           12),
    "intelligence artificielle": ("Tech/IA",    15),
    "machine learning":  ("Tech/IA",            15),
    "data":              ("Tech/IA",            10),
    "ERP":               ("Industrie/RH",       10),
    "infrastructure":    ("Tech",               8),
    "développement":     ("Tech",               6),
    "logiciel":          ("Tech",               6),
    "informatique":      ("Tech",               5),
    "intégration":       ("Tech",               8),
}


@dataclass
class BoampTender:
    title: str
    description: str
    url: str
    published: str
    buyer_name: str
    detected_tech: str
    sector_hint: str
    priority_boost: int
    raw: dict


class BoampCollector(BaseCollector):
    name = "boamp"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=20))
    async def _fetch_api(self, tech: str, limit: int = 30) -> list[BoampTender]:
        """Fetch tenders from the BOAMP Open Data API (data.economie.gouv.fr)."""
        params = {
            "where": f'objet like "{tech}"',
            "limit": limit,
            "order_by": "dateparution desc",
        }
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            r = await client.get(BOAMP_API_URL, params=params)
            r.raise_for_status()

        data = r.json()
        tenders = []
        sector, boost = TECH_KEYWORDS.get(tech, ("Tech", 6))

        for rec in data.get("results", []):
            title = rec.get("objet", "")[:200]
            buyer = rec.get("nomacheteur", "")[:100]
            url = rec.get("url_avis", "") or f"https://www.boamp.fr/avis/detail/{rec.get('idweb','')}"
            pub = rec.get("dateparution", "")
            desc = f"Appel d'offres public — {rec.get('nature_libelle','')} — {rec.get('procedure_libelle','')}"

            if not buyer or not title:
                continue

            tenders.append(BoampTender(
                title=title,
                description=desc[:400],
                url=url,
                published=pub,
                buyer_name=buyer,
                detected_tech=tech,
                sector_hint=sector,
                priority_boost=boost,
                raw={"idweb": rec.get("idweb"), "objet": title, "acheteur": buyer, "pub": pub},
            ))

        return tenders

    async def _fetch_all(self) -> list[BoampTender]:
        all_tenders: list[BoampTender] = []
        seen: set[str] = set()
        for tech in TECH_KEYWORDS:
            try:
                tenders = await self._fetch_api(tech, limit=20)
                for t in tenders:
                    key = f"{t.buyer_name}:{t.detected_tech}"
                    if key not in seen:
                        seen.add(key)
                        all_tenders.append(t)
                logger.info(f"BOAMP '{tech}': {len(tenders)} appels d'offres")
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning(f"BOAMP fetch failed for '{tech}': {e}")
        logger.info(f"BOAMP total: {len(all_tenders)} appels d'offres IT filtrés")
        return all_tenders

    async def collect(self, dry_run: bool = False) -> int:
        self.log_start()
        try:
            tenders = await self._fetch_all()
            if not tenders:
                logger.warning("BOAMP: aucun appel d'offres IT trouvé")
                return 0

            if dry_run:
                for t in tenders:
                    logger.info(
                        f"[DRY RUN] BOAMP: {t.buyer_name or 'Acheteur public'} | "
                        f"{t.detected_tech} | {t.title[:60]}"
                    )
                return 0

            from pipeline.ingest import ingest_raw_dict
            count = 0
            for t in tenders:
                buyer = t.buyer_name or "Acheteur public BOAMP"
                slug = buyer.lower().replace(" ", "-").replace(",", "")[:50]
                ingested = await ingest_raw_dict({
                    "company_name": buyer,
                    "company_linkedin_url": f"https://boamp.fr/acheteur/{slug}",
                    "company_universal_name": slug,
                    "job_title": t.title[:120],
                    "job_url": t.url,
                    "location": "France",
                    "country_iso": "FR",
                    "technology": t.detected_tech,
                    "sector_hint": t.sector_hint,
                    "priority_boost": t.priority_boost,
                    "raw_job": t.raw,
                    "opportunity_type": "b2b_tender",
                }, source_platform="boamp")
                if ingested:
                    count += 1
                    logger.success(f"BOAMP ingéré: {buyer} | {t.detected_tech}")
                await asyncio.sleep(0.2)

            self.log_done(count)
            return count

        except Exception as e:
            logger.error(f"BOAMP collection failed: {e}")
            return 0


def _extract_buyer(title: str, desc: str) -> str:
    """Best-effort extraction of the buying organization name."""
    for text in [title, desc]:
        for separator in [" - ", " | ", " — ", "Acheteur : ", "Pouvoir adjudicateur : "]:
            if separator in text:
                parts = text.split(separator)
                candidate = parts[-1].strip()[:80]
                if len(candidate) > 3:
                    return candidate
    return ""
