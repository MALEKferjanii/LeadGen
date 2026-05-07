"""
Point central d'ingestion. Appelé par tous les collecteurs.
Responsabilités :
  1. Normaliser la donnée brute vers le schéma DB
  2. Dédupliquer (upsert par linkedin_url)
  3. Appliquer le score règle-métier (avant NLP)
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING
from loguru import logger
from db.client import get_pool
from pipeline.scorer_rules import compute_rule_score

if TYPE_CHECKING:
    from collectors.linkedin_hiring import HiringProspect


async def ingest_opportunity(
    prospect: "HiringProspect",
    source_platform: str = "linkedin_jobs",
    opportunity_type: str = "outsourcing_signal",
) -> bool:
    """
    Normalise, déduplique et insère un prospect.
    Retourne True si c'est un nouvel enregistrement, False si doublon.

    opportunity_type valeurs :
      - outsourcing_signal : signal indirect via offre d'emploi IT
      - b2b_rfp            : Demande de Proposition / RFP direct
      - b2b_tender         : Appel d'offres public ou privé
      - b2b_subcontracting : Sous-traitance / externalisation
      - b2b_partnership    : Partenariat / co-traitance
    """
    pool = await get_pool()

    async with pool.acquire() as conn:
        raw_data = json.dumps(prospect.raw_job, default=str, ensure_ascii=False)

        # 1. Upsert entreprise
        company_id = await conn.fetchval(
            """
            INSERT INTO companies (name, linkedin_url, country, sector, source, raw_data)
            VALUES ($1, $2, $3, $4, 'linkedin_hiring', $5::jsonb)
            ON CONFLICT (linkedin_url) DO UPDATE
                SET name       = EXCLUDED.name,
                    updated_at = NOW()
            RETURNING id
            """,
            prospect.company_name,
            prospect.company_linkedin_url,
            prospect.country_iso,
            prospect.sector_hint,
            raw_data,
        )

        # 2. Dédupliquer : même entreprise + même techno + même type dans les 30 derniers jours
        existing = await conn.fetchval(
            """
            SELECT id FROM opportunities
            WHERE company_id = $1
              AND $2 = ANY(technologies)
              AND opportunity_type = $3
              AND created_at > NOW() - INTERVAL '30 days'
            """,
            company_id,
            prospect.technology,
            opportunity_type,
        )

        if existing:
            logger.debug(
                f"Doublon ignoré: {prospect.company_name} / {prospect.technology}"
            )
            return False

        # 3. Score règle-métier
        rule_score = compute_rule_score(
            country=prospect.country_iso,
            sector_hint=prospect.sector_hint,
            technology=prospect.technology,
            priority_boost=prospect.priority_boost,
        )

        # 4. Titre adapté selon le type de signal
        type_labels = {
            "outsourcing_signal": "[Signal externalisation]",
            "b2b_rfp":            "[RFP/DDP]",
            "b2b_tender":         "[Appel d'offres]",
            "b2b_subcontracting": "[Sous-traitance]",
            "b2b_partnership":    "[Partenariat]",
        }
        label = type_labels.get(opportunity_type, "[Signal B2B]")

        # 5. Insertion
        opp_id = await conn.fetchval(
            """
            INSERT INTO opportunities (
                company_id, title, description, opportunity_type,
                technologies, source_url, source_platform,
                country, priority_score, sector_label, status
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'new')
            RETURNING id
            """,
            company_id,
            f"{label} {prospect.technology} — {prospect.company_name}",
            (
                f"{label} {prospect.technology} "
                f"à {prospect.location}. Détail: {prospect.job_title}."
            ),
            opportunity_type,
            [prospect.technology],
            prospect.job_url,
            source_platform,
            prospect.country_iso,
            rule_score,
            prospect.sector_hint,
        )

        logger.info(
            f"Nouvelle opportunité | id={opp_id} | "
            f"entreprise={prospect.company_name} | tech={prospect.technology} | "
            f"pays={prospect.country_iso} | score={rule_score}"
        )
        return True


async def ingest_raw_dict(
    data: dict,
    source_platform: str = "linkedin_jobs",
    opportunity_type: str | None = None,
) -> bool:
    """
    Entrée alternative pour l'API /ingest (n8n webhooks) et collecteurs non-LinkedIn.
    Accepte un dict normalisé avec les mêmes champs que HiringProspect.
    Le champ 'opportunity_type' peut être dans data ou passé en paramètre.
    """
    from collectors.linkedin_hiring import HiringProspect
    try:
        prospect = HiringProspect(
            company_name=data.get("company_name", ""),
            company_linkedin_url=data.get("company_linkedin_url", ""),
            company_universal_name=data.get("company_universal_name", ""),
            job_title=data.get("job_title", ""),
            job_url=data.get("job_url", ""),
            location=data.get("location", ""),
            country_iso=data.get("country_iso", "FR"),
            technology=data.get("technology", ""),
            sector_hint=data.get("sector_hint", "Tech"),
            priority_boost=int(data.get("priority_boost", 5)),
            raw_job=data.get("raw_job", data),
        )
        opp_type = opportunity_type or data.get("opportunity_type", "b2b_tender")
        return await ingest_opportunity(prospect, source_platform=source_platform, opportunity_type=opp_type)
    except Exception as e:
        logger.error(f"ingest_raw_dict failed: {e}")
        return False
