"""
COLLECTEUR DIRECT B2B — Signaux RFP / AO / partenariat / sous-traitance sur LinkedIn.

Stratégie :
  1. Chercher des ENTREPRISES ACHETEUSES IT (banques, assurances, industrie, santé)
     via search_companies() avec des mots-clés sectoriels
  2. Récupérer leurs publications récentes via get_company_updates_by_id()
  3. Détecter les posts qui expriment un besoin de prestataire/partenaire externe

Types de signaux :
  b2b_rfp            : RFP, DDP, demande de proposition
  b2b_tender         : Appel d'offres, consultation
  b2b_subcontracting : Sous-traitance, externalisation, recherche prestataire
  b2b_partnership    : Partenariat, co-traitance, consortium

N.B. : linkedin_hiring.py couvre les signaux INDIRECTS (offres emploi IT →
       opportunity_type = 'outsourcing_signal').
"""
from __future__ import annotations

import asyncio
import hashlib
import random
import re
from loguru import logger

from collectors.base import BaseCollector

# ── Recherches d'entreprises acheteuses IT (secteurs non-IT) ─────────────────
# (keywords, secteur, boost_base)
BUYER_SEARCH_QUERIES: list[tuple[str, str, int]] = [
    # Finance / Banque
    ("banque crédit financement France",            "Finance/Banque",    20),
    ("assurance mutuelle France prévoyance",        "Finance/Assurance", 18),
    ("caisse épargne crédit populaire",             "Finance/Banque",    20),
    # Secteur public / Collectivités
    ("mairie métropole communauté agglomération",   "Secteur public",    14),
    ("région département conseil général France",   "Secteur public",    13),
    ("hôpital CHU santé publique France",           "Santé",             14),
    # Industrie / Manufacturing
    ("groupe industriel France fabrication usine",  "Industrie/RH",      14),
    ("énergie électricité réseau infrastructure",   "Energie",           15),
    ("transport logistique France supply chain",    "Transport",         13),
    # Retail / Grande conso
    ("distribution retail commerce grande surface", "Retail",            12),
    # Tunisie
    ("banque tunisie financement",                  "Finance/Banque",    18),
    ("entreprise industrielle tunisie production",  "Industrie/RH",      14),
]

# ── Patterns de détection B2B dans les posts ─────────────────────────────────
# (pattern, opportunity_type, boost_extra)
_B2B_SIGNALS: list[tuple[re.Pattern, str, int]] = [
    # RFP / DDP
    (re.compile(r'\b(rfp|request for proposal|demande de proposition|ddp|appel à propositions)\b', re.I),
     "b2b_rfp", 22),
    # Appel d'offres
    (re.compile(r'\b(appel d.offres?|appel à candidature|ao |marché public|consultation|mise en concurrence)\b', re.I),
     "b2b_tender", 18),
    # Sous-traitance / prestataire
    (re.compile(r'\b(recherche (un |une |des )?prestataire|sous.traitan|externalisa|recherche (un |une )?partenaire|outsourc)\b', re.I),
     "b2b_subcontracting", 16),
    # Partenariat
    (re.compile(r'\b(partenariat stratégique|co.traitan|consortium|recherche partenaire (technolog|IT|informati))\b', re.I),
     "b2b_partnership", 14),
    # Sélection / choix de prestataire (post-RFP)
    (re.compile(r'\b(sélection(né|ner)?|retenu|choisi).{0,40}(prestataire|fournisseur|partenaire)\b', re.I),
     "b2b_tender", 12),
]

# Technologies qui augmentent la priorité
_TECH_BOOST: list[tuple[re.Pattern, str, int]] = [
    (re.compile(r'\bCOBOL\b', re.I),                        "COBOL",          10),
    (re.compile(r'\bMainframe\b', re.I),                     "Mainframe",      10),
    (re.compile(r'\bSAP\b'),                                  "SAP",             6),
    (re.compile(r'\bJava\b', re.I),                          "Java",            4),
    (re.compile(r'\bPython\b', re.I),                        "Python",          5),
    (re.compile(r'\bDevOps\b', re.I),                        "DevOps",          5),
    (re.compile(r'\b(data engineer|big data|datalake)\b', re.I), "Data Engineer", 5),
    (re.compile(r'\b(machine learning|IA|intelligence artificielle)\b', re.I), "Machine Learning", 6),
    (re.compile(r'\b(cloud|AWS|Azure|GCP)\b', re.I),         "Cloud",           4),
    (re.compile(r'\bERP\b'),                                  "ERP",             5),
    (re.compile(r'\bcybers[eé]curit[eé]\b', re.I),           "Cybersécurité",   6),
    (re.compile(r'\binfrastructure\b', re.I),                "Infrastructure",   3),
]

# Mots qui indiquent que la société EST un ESN/prestataire (à exclure)
_ESN_INDICATORS = re.compile(
    r'\b(ESN|SSII|société de services informatiques|cabinet de conseil IT|consulting firm'
    r'|nous accompagnons|nos experts|notre expertise|nos consultants|nos solutions)\b',
    re.I
)


def _score_post(text: str) -> tuple[str | None, str, int]:
    """
    Analyse le texte d'un post.
    Retourne (opportunity_type | None, technology, total_boost).
    None = pas de signal B2B direct.
    """
    opp_type = None
    base_boost = 0

    for pattern, otype, boost in _B2B_SIGNALS:
        if pattern.search(text):
            if boost > base_boost:
                opp_type = otype
                base_boost = boost

    if not opp_type:
        return None, "Informatique", 0

    # Technologie
    tech = "Informatique"
    tech_boost = 0
    for pattern, t, tb in _TECH_BOOST:
        if pattern.search(text):
            if tb > tech_boost:
                tech = t
                tech_boost = tb

    return opp_type, tech, base_boost + tech_boost


def _extract_post_text(update: dict) -> str:
    """Extrait le texte d'un post get_company_updates()."""
    try:
        inner = update.get("value", {}).get(
            "com.linkedin.voyager.feed.render.UpdateV2", {}
        )
        # Primary path: commentary.text.text
        commentary = inner.get("commentary", {})
        if isinstance(commentary, dict):
            text_obj = commentary.get("text", {})
            if isinstance(text_obj, dict):
                return text_obj.get("text", "")
            return str(text_obj)
        # Fallback: socialContent description
        social = inner.get("socialContent", {})
        if social:
            desc = social.get("description", {})
            if isinstance(desc, dict):
                return desc.get("text", "")
    except Exception:
        pass
    return ""


class LinkedInB2BCollector(BaseCollector):
    name = "linkedin_b2b"

    def __init__(self, client=None):
        self._client = client

    def set_client(self, client):
        self._client = client

    async def _scan_company(
        self,
        urn_id: str,
        company_name: str,
        sector: str,
        base_boost: int,
    ) -> list[dict]:
        """
        Récupère les posts récents d'une entreprise et filtre
        ceux qui contiennent un signal B2B exploitable.
        """
        updates = await self._client.get_company_updates_by_id(urn_id, max_results=15)
        signals = []
        for update in updates:
            text = _extract_post_text(update)
            if not text or len(text) < 40:
                continue

            # Exclure si l'entreprise EST un ESN qui parle de ses propres services
            if _ESN_INDICATORS.search(text[:200]):
                continue

            opp_type, tech, extra_boost = _score_post(text)
            if not opp_type:
                continue

            signals.append({
                "company_name": company_name,
                "urn_id": urn_id,
                "post_text": text[:300],
                "opportunity_type": opp_type,
                "technology": tech,
                "sector_hint": sector,
                "priority_boost": min(base_boost + extra_boost, 30),
                "post_id": hashlib.md5(
                    f"{company_name}:{text[:80]}".encode()
                ).hexdigest(),
            })
        return signals

    async def collect(self, dry_run: bool = False) -> int:
        self.log_start()
        if not self._client:
            logger.error("LinkedInB2BCollector: client LinkedIn non initialisé")
            return 0

        total = 0
        seen_keys: set[str] = set()

        for search_query, sector, boost in BUYER_SEARCH_QUERIES:
            try:
                companies = await self._client.search_companies(
                    keywords=search_query, limit=8
                )
                logger.info(
                    f"LinkedIn B2B '{search_query[:40]}': {len(companies)} entreprises"
                )

                for company in companies:
                    name = company.get("name", "")
                    urn_id = str(company.get("urn_id", ""))
                    if not name or not urn_id:
                        continue

                    try:
                        signals = await self._scan_company(
                            urn_id, name, sector, boost
                        )
                    except Exception as e:
                        logger.debug(f"scan_company({name!r}): {e}")
                        continue

                    for sig in signals:
                        key = sig["post_id"]
                        if key in seen_keys:
                            continue
                        seen_keys.add(key)

                        if dry_run:
                            logger.info(
                                f"[DRY RUN] B2B: {sig['company_name']} | "
                                f"{sig['opportunity_type']} | {sig['technology']} | "
                                f"{sig['post_text'][:100]}"
                            )
                            continue

                        from pipeline.ingest import ingest_raw_dict
                        urn = sig["urn_id"]
                        ingested = await ingest_raw_dict({
                            "company_name": sig["company_name"],
                            "company_linkedin_url": f"https://linkedin.com/company/{urn}",
                            "company_universal_name": f"li-{urn}",
                            "job_title": sig["post_text"][:120],
                            "job_url": f"https://linkedin.com/company/{urn}/posts/",
                            "location": "France",
                            "country_iso": "FR",
                            "technology": sig["technology"],
                            "sector_hint": sig["sector_hint"],
                            "priority_boost": sig["priority_boost"],
                            "opportunity_type": sig["opportunity_type"],
                            "raw_job": sig,
                        }, source_platform="linkedin_b2b")

                        if ingested:
                            total += 1
                            logger.success(
                                f"B2B ingéré: {sig['company_name']} | "
                                f"{sig['opportunity_type']} | {sig['technology']}"
                            )

                    await asyncio.sleep(random.uniform(1.5, 2.5))

            except Exception as e:
                logger.warning(
                    f"LinkedIn B2B '{search_query[:40]}' failed: {e}"
                )

            await asyncio.sleep(random.gauss(3.0, 0.8))

        self.log_done(total)
        return total
