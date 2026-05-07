"""
COLLECTEUR INDIRECT — Signal d'embauche comme proxy de besoin IT externalisable.

Logique B2B : une entreprise qui recrute activement des dev IT a un besoin non satisfait.
Solvinya peut proposer une équipe externalisée AVANT qu'ils finalisent le recrutement.
C'est un signal INDIRECT (contrairement aux RFP/AO collectés par linkedin_b2b.py).

Les offres d'emploi ne sont PAS des opportunités pour des candidats individuels —
elles signalent que l'entreprise a un projet IT actif avec budget disponible.
opportunity_type = 'outsourcing_signal' dans la DB.
"""
from __future__ import annotations

import asyncio
import random
import sys
from dataclasses import dataclass
from typing import Optional
from loguru import logger

from collectors.linkedin_client import LinkedInClient
from pipeline.ingest import ingest_opportunity

# Mapping technologies → secteur hint et boost de priorité Solvinya
TECH_TARGETS: dict[str, dict] = {
    "Java":             {"sector_hint": "Finance/Assurance", "priority_boost": 10},
    "Python":           {"sector_hint": "Tech/IA",           "priority_boost": 15},
    "COBOL":            {"sector_hint": "Finance/Banque",    "priority_boost": 25},  # Rare = haute valeur
    "Mainframe":        {"sector_hint": "Finance/Banque",    "priority_boost": 25},
    "DevOps":           {"sector_hint": "Tech",              "priority_boost": 10},
    "SAP":              {"sector_hint": "Industrie/RH",      "priority_boost": 12},
    "Salesforce":       {"sector_hint": "CRM/Retail",        "priority_boost": 8},
    "React":            {"sector_hint": "Tech/e-commerce",   "priority_boost": 5},
    "Data Engineer":    {"sector_hint": "Tech/IA",           "priority_boost": 12},
    "Machine Learning": {"sector_hint": "IA",                "priority_boost": 15},
}

# (nom_localisation, code_iso, limite_résultats)
TARGET_LOCATIONS: list[tuple[str, str, int]] = [
    ("France",      "FR", 30),
    ("Belgium",     "BE", 20),
    ("Luxembourg",  "LU", 15),
    ("Switzerland", "CH", 15),
    ("Tunisie",     "TN", 20),
]


@dataclass
class HiringProspect:
    company_name: str
    company_linkedin_url: str
    company_universal_name: str
    job_title: str
    job_url: str
    location: str
    country_iso: str
    technology: str
    sector_hint: str
    priority_boost: int
    raw_job: dict


async def collect_hiring_signals(
    client: LinkedInClient,
    dry_run: bool = False,
    tech_filter: str | None = None,
    location_filter: str | None = None,
    limit_override: int | None = None,
) -> int:
    """
    Boucle de collecte principale.
    Retourne le nombre de nouveaux prospects ingérés.
    """
    seen_companies: set[str] = set()
    total_ingested = 0

    techs = {tech_filter: TECH_TARGETS[tech_filter]} if tech_filter and tech_filter in TECH_TARGETS else TECH_TARGETS
    locations = [loc for loc in TARGET_LOCATIONS if not location_filter or loc[0] == location_filter]

    for tech, meta in techs.items():
        for location_name, country_iso, limit in locations:
            actual_limit = limit_override or limit
            logger.info(f"Recherche jobs: '{tech}' à {location_name} (limite={actual_limit})")

            jobs = await client.search_jobs(
                keywords=tech,
                location=location_name,
                limit=actual_limit,
            )

            logger.info(f"{len(jobs)} offres trouvées pour {tech} / {location_name}")

            for job in jobs:
                job_id = job.get("entityUrn", "").split(":")[-1]
                if not job_id:
                    continue

                # Fetch full job details to get company info
                full_job = await client.get_job(job_id)
                if not full_job:
                    continue

                company_name, universal_name = _extract_company_info(full_job)
                if not universal_name or universal_name in seen_companies:
                    continue
                seen_companies.add(universal_name)

                prospect = HiringProspect(
                    company_name=company_name or universal_name,
                    company_linkedin_url=f"https://linkedin.com/company/{universal_name}",
                    company_universal_name=universal_name,
                    job_title=full_job.get("title", job.get("title", "")),
                    job_url=_extract_job_url(full_job) or _extract_job_url(job),
                    location=full_job.get("formattedLocation", location_name),
                    country_iso=country_iso,
                    technology=tech,
                    sector_hint=meta["sector_hint"],
                    priority_boost=meta["priority_boost"],
                    raw_job=full_job,
                )

                if dry_run:
                    logger.info(
                        f"[DRY RUN] Prospect: {prospect.company_name} | "
                        f"tech={tech} | pays={country_iso} | poste={prospect.job_title[:60]}"
                    )
                    continue

                ingested = await ingest_opportunity(
                    prospect, source_platform="linkedin_jobs",
                    opportunity_type="outsourcing_signal",
                )
                if ingested:
                    total_ingested += 1
                    logger.success(
                        f"Ingéré: {prospect.company_name} | {tech} | "
                        f"{country_iso} | boost={meta['priority_boost']}"
                    )

            # Anti-détection : délai gaussien entre chaque combinaison tech/lieu
            if not dry_run:
                delay = max(2.0, random.gauss(4.0, 1.5))
                logger.debug(f"Attente {delay:.1f}s avant la prochaine recherche")
                await asyncio.sleep(delay)

    logger.info(f"Collecte terminée. Total ingéré: {total_ingested}")
    return total_ingested


def _extract_company_info(full_job: dict) -> tuple[str, str]:
    """Extract (company_name, universal_name) from a full get_job() response."""
    try:
        company_details = full_job.get("companyDetails", {})
        for key in company_details:
            resolution = company_details[key].get("companyResolutionResult", {})
            name = resolution.get("name", "")
            universal = resolution.get("universalName", "")
            if universal:
                return name, universal.lower().strip()
    except Exception:
        pass
    return "", ""


def _extract_job_url(job: dict) -> str:
    try:
        job_id = job.get("entityUrn", "").split(":")[-1]
        if job_id:
            return f"https://linkedin.com/jobs/view/{job_id}"
    except Exception:
        pass
    return ""


# ─── Point d'entrée CLI ────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    from collectors.session_manager import SessionManager

    parser = argparse.ArgumentParser(description="LinkedIn Hiring Signal Collector")
    parser.add_argument("--dry-run", action="store_true", help="Simuler sans insérer en DB")
    parser.add_argument("--tech", help="Filtrer sur une technologie spécifique")
    parser.add_argument("--location", help="Filtrer sur un pays spécifique")
    parser.add_argument("--limit", type=int, help="Surcharger la limite de résultats")
    args = parser.parse_args()

    async def main():
        session = SessionManager()
        await session.initialize()
        client = session.get_client()
        n = await collect_hiring_signals(
            client,
            dry_run=args.dry_run,
            tech_filter=args.tech,
            location_filter=args.location,
            limit_override=args.limit,
        )
        print(f"\nTotal ingéré: {n} prospects")

    asyncio.run(main())
