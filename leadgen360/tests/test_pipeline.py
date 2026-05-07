"""Tests pipeline ingest + scorer règle-métier."""
import pytest
from pipeline.scorer_rules import compute_rule_score
from pipeline.ingest import ingest_opportunity
from collectors.linkedin_hiring import HiringProspect


class TestRuleScorer:
    def test_lu_cobol_finance_max_score(self):
        score = compute_rule_score("LU", "Finance/Banque", "COBOL", priority_boost=25)
        assert score >= 90, f"LU+COBOL+Finance devrait scorer >= 90, got {score}"

    def test_tn_react_retail_low_score(self):
        score = compute_rule_score("TN", "Tech/e-commerce", "React", priority_boost=5)
        assert score <= 65, f"TN+React+Retail devrait scorer <= 65, got {score}"

    def test_score_bounded_0_100(self):
        for country in ["FR", "BE", "LU", "CH", "TN", "XX"]:
            for tech in ["COBOL", "React", "SAP", "Unknown"]:
                score = compute_rule_score(country, "Finance", tech, priority_boost=0)
                assert 0 <= score <= 100, f"Score hors bornes: {score} pour {country}/{tech}"

    def test_fr_java_finance_medium_high(self):
        score = compute_rule_score("FR", "Finance/Assurance", "Java", priority_boost=10)
        assert 65 <= score <= 95, f"FR+Java+Finance devrait être entre 65-95, got {score}"

    def test_priority_boost_impact(self):
        base  = compute_rule_score("FR", "Tech", "Python", priority_boost=0)
        boosted = compute_rule_score("FR", "Tech", "Python", priority_boost=25)
        assert boosted > base, "Un priority_boost plus élevé doit augmenter le score"


class TestIngest:
    @pytest.mark.asyncio
    async def test_ingest_new_prospect(self, mock_pool):
        """Un nouveau prospect doit retourner True."""
        from unittest.mock import AsyncMock
        mock_pool.conn.fetchval = AsyncMock(side_effect=[
            "00000000-0000-0000-0000-000000000001",  # company upsert
            None,                                     # pas de doublon
            "00000000-0000-0000-0000-000000000002",  # opp insert
        ])

        prospect = HiringProspect(
            company_name="BNP Paribas",
            company_linkedin_url="https://linkedin.com/company/bnp-paribas",
            company_universal_name="bnp-paribas",
            job_title="Développeur COBOL Senior",
            job_url="https://linkedin.com/jobs/view/123",
            location="Paris, France",
            country_iso="FR",
            technology="COBOL",
            sector_hint="Finance/Banque",
            priority_boost=25,
            raw_job={"test": True},
        )

        result = await ingest_opportunity(prospect)
        assert result is True

    @pytest.mark.asyncio
    async def test_ingest_duplicate_returns_false(self, mock_pool):
        """Un doublon doit retourner False sans insertion."""
        from unittest.mock import AsyncMock
        mock_pool.conn.fetchval = AsyncMock(side_effect=[
            "00000000-0000-0000-0000-000000000001",  # company upsert
            "00000000-0000-0000-0000-000000000099",  # doublon trouvé
        ])

        prospect = HiringProspect(
            company_name="Société Générale",
            company_linkedin_url="https://linkedin.com/company/societe-generale",
            company_universal_name="societe-generale",
            job_title="DevOps Engineer",
            job_url="https://linkedin.com/jobs/view/456",
            location="La Défense, France",
            country_iso="FR",
            technology="DevOps",
            sector_hint="Finance",
            priority_boost=10,
            raw_job={},
        )

        result = await ingest_opportunity(prospect)
        assert result is False
