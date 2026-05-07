"""Tests classificateur NLP — vérifie les prédictions sur des exemples clés."""
import pytest
from nlp.classifier import OpportunityClassifier
from nlp.data.training_data import TRAINING_DATA
from nlp.scorer import compute_nlp_score


@pytest.fixture(scope="module")
def trained_clf():
    """Entraîne le classificateur une seule fois pour tous les tests du module."""
    clf = OpportunityClassifier()
    clf.train(TRAINING_DATA)
    return clf


class TestClassifier:
    def test_cobol_finance_prediction(self, trained_clf):
        text = "Développeur COBOL senior pour système bancaire mainframe Luxembourg"
        result = trained_clf.predict(text)
        assert result["sector_label"] in ("Finance", "Public"), \
            f"COBOL bancaire devrait être Finance ou Public, got {result['sector_label']}"
        assert result["priority_label"] == "high", \
            f"COBOL finance devrait être high priority, got {result['priority_label']}"

    def test_ml_tech_prediction(self, trained_clf):
        text = "Machine Learning engineer pour modèle recommandation e-commerce"
        result = trained_clf.predict(text)
        assert result["tech_label"] == "Machine Learning", \
            f"ML engineer devrait être tech=Machine Learning, got {result['tech_label']}"

    def test_devops_retail_prediction(self, trained_clf):
        text = "DevOps CI/CD Kubernetes pour grande distribution, pipeline Jenkins"
        result = trained_clf.predict(text)
        assert result["sector_label"] in ("Retail", "Tech", "Industrie"), \
            f"DevOps grande distribution: secteur inattendu {result['sector_label']}"

    def test_confidence_between_0_and_1(self, trained_clf):
        result = trained_clf.predict("Développeur Java Spring Boot API REST")
        assert 0.0 <= result["sector_confidence"] <= 1.0
        assert 0.0 <= result["tech_confidence"] <= 1.0
        assert 0.0 <= result["priority_confidence"] <= 1.0

    def test_all_required_keys_present(self, trained_clf):
        result = trained_clf.predict("SAP ABAP consultant Industrie 4.0")
        required = {"sector_label", "sector_confidence", "tech_label", "tech_confidence",
                    "priority_label", "priority_confidence"}
        assert required.issubset(result.keys()), f"Clés manquantes: {required - result.keys()}"

    def test_agriculture_low_priority(self, trained_clf):
        text = "Application mobile agriculteur suivi météo cultures GPS terrain"
        result = trained_clf.predict(text)
        assert result["priority_label"] in ("low", "medium"), \
            f"Agriculture devrait être low/medium, got {result['priority_label']}"

    def test_sap_industrie_detection(self, trained_clf):
        text = "SAP S/4HANA consultant implémentation industrie automobile Tier 1"
        result = trained_clf.predict(text)
        assert result["tech_label"] == "SAP", \
            f"SAP S/4HANA devrait détecter tech=SAP, got {result['tech_label']}"


class TestNLPScorer:
    def test_high_priority_boosts_score(self):
        pred_high = {"priority_label": "high", "priority_confidence": 0.95, "sector_label": "Finance"}
        pred_low  = {"priority_label": "low",  "priority_confidence": 0.90, "sector_label": "Retail"}
        score_high = compute_nlp_score(80, pred_high)
        score_low  = compute_nlp_score(80, pred_low)
        assert score_high > score_low, "High priority devrait scorer plus que low"

    def test_score_always_bounded(self):
        for priority in ["high", "medium", "low"]:
            for sector in ["Finance", "Agriculture", "Tech", "Startup"]:
                pred = {"priority_label": priority, "priority_confidence": 0.99, "sector_label": sector}
                for rule in [0, 50, 100]:
                    score = compute_nlp_score(rule, pred)
                    assert 0 <= score <= 100, f"Score {score} hors bornes pour {priority}/{sector}"
