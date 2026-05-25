"""
Suite d'évaluation complète. Génère :
  - Matrice de confusion (PNG)
  - Rapport classification (precision/recall/f1 par classe)
  - Cross-validation 5-fold
  - JSON résumé pour le rapport final (jury)
"""
from __future__ import annotations

import json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.metrics import (
    confusion_matrix,
    classification_report,
    ConfusionMatrixDisplay,
)
from sklearn.model_selection import train_test_split, cross_val_score
from pathlib import Path
from loguru import logger

from nlp.classifier import OpportunityClassifier

REPORTS_DIR = Path("nlp/reports")


def evaluate(clf: OpportunityClassifier, data: list[tuple]) -> dict:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    texts      = [d[0] for d in data]
    sectors    = [d[1] for d in data]
    priorities = [d[3] for d in data]

    X = clf._embed(texts)

    # Split stratifié secteur
    X_train, X_test, y_sec_train, y_sec_test = train_test_split(
        X, sectors, test_size=0.2, random_state=42, stratify=sectors
    )
    _, _, y_pri_train, y_pri_test = train_test_split(
        X, priorities, test_size=0.2, random_state=42, stratify=priorities
    )

    # ─── Évaluation secteur (entraîné sur X_train, testé sur X_test) ────────
    # On entraîne un classificateur frais sur X_train pour évaluation honnête
    from sklearn.svm import LinearSVC
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.linear_model import LogisticRegression as LR

    y_sec_train_enc = clf.sector_le.transform(y_sec_train)
    y_sec_test_enc  = clf.sector_le.transform(y_sec_test)

    # Utilise le même type de modèle que l'entraînement principal
    from sklearn.svm import LinearSVC as _LSVC
    from sklearn.calibration import CalibratedClassifierCV as _CCCV
    if getattr(clf, "_embedding_mode", "") == "tfidf":
        eval_sector_clf = _CCCV(_LSVC(C=3.0, max_iter=5000, random_state=42), cv=3)
    else:
        eval_sector_clf = _CCCV(_LSVC(C=5.0, max_iter=5000, random_state=42), cv=3)
    eval_sector_clf.fit(X_train, y_sec_train_enc)
    y_sec_pred = eval_sector_clf.predict(X_test)

    sector_report = classification_report(
        y_sec_test_enc,
        y_sec_pred,
        target_names=clf.sector_le.classes_,
        output_dict=True,
        zero_division=0,
    )

    # Matrice de confusion — secteur
    cm = confusion_matrix(y_sec_test_enc, y_sec_pred)
    fig, ax = plt.subplots(figsize=(12, 9))
    ConfusionMatrixDisplay(cm, display_labels=clf.sector_le.classes_).plot(
        ax=ax, colorbar=True, cmap="Blues", xticks_rotation=45
    )
    ax.set_title("Matrice de Confusion — Classification Secteur", fontsize=13, pad=15)
    plt.tight_layout()
    cm_path = REPORTS_DIR / "confusion_matrix_sector.png"
    plt.savefig(cm_path, dpi=150)
    plt.close()
    logger.success(f"Matrice de confusion sauvegardée : {cm_path}")

    # Cross-validation (sur l'ensemble complet, même architecture que l'entraînement)
    y_all_enc = clf.sector_le.transform(sectors)
    from sklearn.svm import LinearSVC as _LSVC2
    from sklearn.calibration import CalibratedClassifierCV as _CCCV2
    if getattr(clf, "_embedding_mode", "") == "tfidf":
        cv_clf = _CCCV2(_LSVC2(C=3.0, max_iter=5000, random_state=42), cv=3)
    else:
        cv_clf = _CCCV2(_LSVC2(C=5.0, max_iter=5000, random_state=42), cv=3)
    cv_scores = cross_val_score(cv_clf, X, y_all_enc, cv=5, scoring="accuracy")

    # ─── Évaluation priorité (idem, entraîné sur X_train) ──────────────────
    y_pri_train_enc = clf.priority_le.transform(y_pri_train)
    y_pri_test_enc  = clf.priority_le.transform(y_pri_test)

    if getattr(clf, "_embedding_mode", "") == "tfidf":
        base_p = LinearSVC(C=3.0, max_iter=5000, random_state=42)
        eval_priority_clf = CalibratedClassifierCV(base_p, cv=3)
    else:
        eval_priority_clf = LR(C=5.0, class_weight="balanced", max_iter=1000, random_state=42)
    eval_priority_clf.fit(X_train, y_pri_train_enc)
    y_pri_pred = eval_priority_clf.predict(X_test)

    priority_report = classification_report(
        y_pri_test_enc,
        y_pri_pred,
        target_names=clf.priority_le.classes_,
        output_dict=True,
        zero_division=0,
    )

    # Matrice de confusion — priorité
    cm_pri = confusion_matrix(y_pri_test_enc, y_pri_pred)
    fig2, ax2 = plt.subplots(figsize=(7, 5))
    ConfusionMatrixDisplay(cm_pri, display_labels=clf.priority_le.classes_).plot(
        ax=ax2, colorbar=True, cmap="Oranges"
    )
    ax2.set_title("Matrice de Confusion — Classification Priorité", fontsize=12)
    plt.tight_layout()
    cm_pri_path = REPORTS_DIR / "confusion_matrix_priority.png"
    plt.savefig(cm_pri_path, dpi=150)
    plt.close()

    summary = {
        "sector_accuracy":     round(sector_report.get("accuracy", 0), 4),
        "sector_macro_f1":     round(sector_report["macro avg"]["f1-score"], 4),
        "sector_cv_mean":      round(float(cv_scores.mean()), 4),
        "sector_cv_std":       round(float(cv_scores.std()), 4),
        "priority_accuracy":   round(priority_report.get("accuracy", 0), 4),
        "priority_macro_f1":   round(priority_report["macro avg"]["f1-score"], 4),
        "n_training_examples": len(data),
        "n_test_examples":     len(y_sec_test),
        "per_sector": {
            k: {
                "precision": round(v["precision"], 3),
                "recall":    round(v["recall"], 3),
                "f1":        round(v["f1-score"], 3),
                "support":   int(v["support"]),
            }
            for k, v in sector_report.items()
            if isinstance(v, dict) and k not in ("macro avg", "weighted avg")
        },
    }

    summary_path = REPORTS_DIR / "evaluation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.success(
        f"Évaluation complète | "
        f"sector_acc={summary['sector_accuracy']:.1%} | "
        f"sector_f1={summary['sector_macro_f1']:.1%} | "
        f"priority_acc={summary['priority_accuracy']:.1%} | "
        f"cv={summary['sector_cv_mean']:.1%} ± {summary['sector_cv_std']:.1%}"
    )
    return summary
