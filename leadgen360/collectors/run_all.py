"""
Lance tous les collecteurs en séquence.
Usage:
  python -m collectors.run_all               # collecte complète
  python -m collectors.run_all --dry-run     # simulation sans DB
  python -m collectors.run_all --source linkedin      # signaux externalisation (offres emploi)
  python -m collectors.run_all --source linkedin_b2b  # signaux directs B2B (posts RFP/AO/etc.)
  python -m collectors.run_all --source boamp
  python -m collectors.run_all --source ted
  python -m collectors.run_all --source malt
"""
import asyncio
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from collectors.boamp import BoampCollector
from collectors.malt import MaltCollector
from collectors.ted import TedCollector


async def run_all(dry_run: bool = False, source_filter: str | None = None):
    results = {}

    # ── LinkedIn B2B (signaux directs : RFP, AO, partenariat, sous-traitance) ─
    if not source_filter or source_filter == "linkedin_b2b":
        from collectors.linkedin_b2b import LinkedInB2BCollector
        from collectors.session_manager import SessionManager
        try:
            session = SessionManager()
            await session.initialize()
            client = session.get_client()
            collector = LinkedInB2BCollector(client=client)
            n = await collector.collect(dry_run=dry_run)
            results["linkedin_b2b"] = n
            logger.success(f"LinkedIn B2B: {n} prospects B2B directs ingérés")
        except Exception as e:
            logger.error(f"LinkedIn B2B collection failed: {e}")
            results["linkedin_b2b"] = 0

    # ── LinkedIn indirect (offres d'emploi = signal externalisation) ──────────
    if not source_filter or source_filter == "linkedin":
        from collectors.linkedin_hiring import collect_hiring_signals
        from collectors.session_manager import SessionManager
        try:
            session = SessionManager()
            await session.initialize()
            client = session.get_client()
            n = await collect_hiring_signals(client, dry_run=dry_run)
            results["linkedin"] = n
            logger.success(f"LinkedIn (externalisation): {n} prospects ingérés")
        except Exception as e:
            logger.error(f"LinkedIn collection failed: {e}")
            results["linkedin"] = 0

    # ── BOAMP ─────────────────────────────────────────────────────────────────
    if not source_filter or source_filter == "boamp":
        try:
            boamp = BoampCollector()
            n = await boamp.collect(dry_run=dry_run)
            results["boamp"] = n
        except Exception as e:
            logger.error(f"BOAMP collection failed: {e}")
            results["boamp"] = 0

    # ── TED (EU Tenders) ──────────────────────────────────────────────────────
    if not source_filter or source_filter == "ted":
        try:
            ted = TedCollector()
            n = await ted.collect(dry_run=dry_run)
            results["ted"] = n
        except Exception as e:
            logger.error(f"TED collection failed: {e}")
            results["ted"] = 0

    # ── Malt ──────────────────────────────────────────────────────────────────
    if not source_filter or source_filter == "malt":
        try:
            malt = MaltCollector()
            n = await malt.collect(dry_run=dry_run)
            results["malt"] = n
        except Exception as e:
            logger.error(f"Malt collection failed: {e}")
            results["malt"] = 0

    total = sum(results.values())
    logger.success(
        f"Collecte terminée | "
        + " | ".join(f"{src}={n}" for src, n in results.items())
        + f" | TOTAL={total}"
    )
    return total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LeadGen 360+ — Run All Collectors")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--source", choices=["linkedin", "linkedin_b2b", "boamp", "malt", "ted"])
    args = parser.parse_args()
    asyncio.run(run_all(dry_run=args.dry_run, source_filter=args.source))
