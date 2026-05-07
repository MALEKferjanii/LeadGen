"""
Point d'entrée entraînement : python -m nlp.trainer
Entraîne, évalue, sauvegarde les modèles et le rapport.
"""
import sys
from pathlib import Path

# Assure que la racine du projet est dans PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from nlp.classifier import OpportunityClassifier
from nlp.evaluator import evaluate
from nlp.data.training_data import TRAINING_DATA


def main():
    logger.info(f"Démarrage entraînement — {len(TRAINING_DATA)} exemples")

    clf = OpportunityClassifier()
    clf.train(TRAINING_DATA)

    summary = evaluate(clf, TRAINING_DATA)
    clf.save()

    sector_acc  = summary["sector_accuracy"]
    sector_f1   = summary["sector_macro_f1"]
    cv_mean     = summary["sector_cv_mean"]
    cv_std      = summary["sector_cv_std"]
    priority_acc= summary["priority_accuracy"]

    print("\n" + "=" * 55)
    print("RAPPORT D'ÉVALUATION NLP — LeadGen Francophone 360+")
    print("=" * 55)
    print(f"Accuracy secteur :      {sector_acc:.1%}")
    print(f"F1-score macro secteur: {sector_f1:.1%}")
    print(f"Cross-val (5-fold) :    {cv_mean:.1%} ± {cv_std:.1%}")
    print(f"Accuracy priorité :     {priority_acc:.1%}")
    print(f"Exemples entraînement : {summary['n_training_examples']}")
    print(f"Exemples test :         {summary['n_test_examples']}")
    print("-" * 55)
    print("Détail par secteur :")
    for sector, metrics in summary["per_sector"].items():
        print(f"  {sector:<15} P={metrics['precision']:.2f}  R={metrics['recall']:.2f}  F1={metrics['f1']:.2f}  n={metrics['support']}")
    print("=" * 55)
    print("Matrice de confusion -> nlp/reports/confusion_matrix_sector.png")
    print("Rapport complet     -> nlp/reports/evaluation_summary.json")

    if cv_mean < 0.75:
        logger.warning(
            f"Cross-val {cv_mean:.1%} < 75% — "
            "Verifiez l'equilibre des classes et la qualite des donnees."
        )
        sys.exit(1)
    else:
        logger.success(f"Cross-val {cv_mean:.1%} >= 75%. Modeles prets pour la production.")


if __name__ == "__main__":
    main()
