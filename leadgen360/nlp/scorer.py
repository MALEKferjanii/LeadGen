"""
Score NLP final 0-100, combinant :
  - Score règle-métier (calculé à l'ingestion)
  - Labels NLP (secteur, tech, priorité) avec leurs confiances
"""

PRIORITY_TO_SCORE = {"high": 85, "medium": 55, "low": 25}

SECTOR_BOOST = {
    "Finance":    15,
    "Energie":    12,
    "Public":     8,
    "Sante":      8,
    "Telecom":    6,
    "Industrie":  5,
    "Automobile": 5,
    "Tech":       3,
    "Startup":    2,
    "Retail":     0,
    "Immobilier": -5,
    "Agriculture": -10,
}


def compute_nlp_score(
    rule_score: int,
    prediction: dict,
    nlp_weight: float = 0.40,
) -> int:
    """
    Fusionne le score règle-métier avec la prédiction NLP.
    nlp_weight: part du score NLP dans le score final (0.4 = 40%)
    """
    priority_label = prediction.get("priority_label", "medium")
    sector_label   = prediction.get("sector_label", "Tech")
    confidence     = prediction.get("priority_confidence", 0.5)

    nlp_base  = PRIORITY_TO_SCORE.get(priority_label, 55)
    boost     = SECTOR_BOOST.get(sector_label, 0)
    nlp_score = min(100, max(0, nlp_base + boost)) * confidence

    final = rule_score * (1 - nlp_weight) + nlp_score * nlp_weight
    return min(100, max(0, round(final)))
