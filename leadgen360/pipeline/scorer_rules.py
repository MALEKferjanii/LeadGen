"""
Score règle-métier appliqué à l'ingestion (avant le NLP).
Déterministe et rapide — pas de modèle requis.

Formule (résultat 0-100) :
  country_score    × 0.30
  technology_score × 0.25
  sector_score     × 0.25
  priority_boost   × 0.20  (métadonnée du collecteur)
"""

COUNTRY_SCORES: dict[str, int] = {
    "LU": 100,  # Très forte densité financière
    "CH": 95,
    "FR": 90,
    "BE": 85,
    "MC": 80,
    "TN": 65,
}

TECHNOLOGY_SCORES: dict[str, int] = {
    "COBOL": 100,           # Legacy rare = forte valeur
    "Mainframe": 100,
    "SAP": 85,
    "Java": 80,
    "Machine Learning": 78,
    "Data Engineer": 75,
    "Python": 70,
    "DevOps": 70,
    "Salesforce": 65,
    "React": 55,
}

SECTOR_SCORES: dict[str, int] = {
    "Finance/Banque": 100,
    "Finance/Assurance": 95,
    "Finance": 90,
    "Assurance": 88,
    "Finance/IA": 85,
    "Industrie/RH": 70,
    "IA": 75,
    "Tech": 65,
    "Tech/IA": 72,
    "CRM/Retail": 60,
    "Tech/e-commerce": 55,
    "Retail": 50,
}


def compute_rule_score(
    country: str,
    sector_hint: str,
    technology: str,
    priority_boost: int = 0,
) -> int:
    c = COUNTRY_SCORES.get(country, 50)
    t = TECHNOLOGY_SCORES.get(technology, 50)
    s = SECTOR_SCORES.get(sector_hint, 50)
    b = min(priority_boost * 4, 100)

    raw = c * 0.30 + t * 0.25 + s * 0.25 + b * 0.20
    return min(100, max(0, round(raw)))
