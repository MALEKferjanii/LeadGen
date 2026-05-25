"""
Classificateur NLP pour opportunités IT francophones.

Modèle primaire  : paraphrase-multilingual-MiniLM-L12-v2 (384-dim embeddings) +
                   LogisticRegression sklearn.
Modèle fallback  : TF-IDF n-grammes (1-3) + LogisticRegression.
                   Utilisé automatiquement si le modèle HF n'est pas téléchargeable.

Trois classificateurs parallèles :
  - sector_clf   : 12 secteurs
  - tech_clf     : 10 technologies
  - priority_clf : 3 niveaux (high / medium / low)
"""
from __future__ import annotations

import numpy as np
from pathlib import Path
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.pipeline import Pipeline
import joblib
from loguru import logger

MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"
MODELS_DIR = Path("nlp/models")

_sentence_transformer = None
_use_tfidf = False


def _load_sentence_transformer():
    """
    Essaie d'abord local_files_only=True (instantané si déjà en cache).
    Si le modèle n'est pas en cache, tente le téléchargement dans un thread
    avec timeout de 15s. Si échec → fallback TF-IDF immédiat.
    """
    global _sentence_transformer, _use_tfidf
    if _sentence_transformer is not None:
        return _sentence_transformer

    import os
    # Permettre un bypass explicite via variable d'environnement
    if os.environ.get("LEADGEN_USE_TFIDF", "").lower() in ("1", "true", "yes"):
        logger.info("LEADGEN_USE_TFIDF=1 → mode TF-IDF forcé")
        _use_tfidf = True
        return None

    try:
        from sentence_transformers import SentenceTransformer

        # 1. Essai local (instantané, pas de réseau)
        try:
            logger.info(f"Recherche du modèle en cache local: {MODEL_NAME}")
            _sentence_transformer = SentenceTransformer(MODEL_NAME, local_files_only=True)
            _use_tfidf = False
            logger.success("Modèle sentence-transformers chargé depuis le cache local")
            return _sentence_transformer
        except Exception:
            logger.info("Modèle non trouvé en cache. Tentative de téléchargement (timeout=30s)...")

        # 2. Tentative de téléchargement avec timeout
        import threading
        result = [None]
        error  = [None]

        def download():
            try:
                result[0] = SentenceTransformer(MODEL_NAME, local_files_only=False)
            except Exception as e:
                error[0] = e

        t = threading.Thread(target=download, daemon=True)
        t.start()
        t.join(timeout=30)

        if result[0] is not None:
            _sentence_transformer = result[0]
            _use_tfidf = False
            logger.success("Modèle sentence-transformers téléchargé et chargé")
            return _sentence_transformer
        else:
            raise Exception(error[0] or "Timeout (30s) lors du téléchargement du modèle")

    except Exception as e:
        logger.warning(
            f"sentence-transformers indisponible: {type(e).__name__}. "
            "Démarrage en mode TF-IDF (fallback). "
            "Pour utiliser le modèle complet : télécharger le modèle et relancer make train."
        )
        _use_tfidf = True
        return None


class OpportunityClassifier:
    def __init__(self):
        self._st_model = None
        self._cache: dict[str, np.ndarray] = {}

        # Classificateurs
        self.sector_clf: LogisticRegression | None = None
        self.tech_clf: LogisticRegression | None = None
        self.priority_clf: LogisticRegression | None = None

        # Label encoders
        self.sector_le = LabelEncoder()
        self.tech_le = LabelEncoder()
        self.priority_le = LabelEncoder()

        # TF-IDF (fallback)
        self._tfidf: TfidfVectorizer | None = None
        self._embedding_mode: str = "unknown"

    def _try_load_st(self):
        if self._st_model is None:
            self._st_model = _load_sentence_transformer()
        return self._st_model

    def _embed(self, texts: list[str]) -> np.ndarray:
        # If mode is already fixed (e.g. loaded from disk), honour it — don't
        # attempt ST even if the library became available after training in TF-IDF mode.
        if self._embedding_mode == "tfidf":
            st = None
        else:
            st = self._try_load_st()

        if st is not None:
            # Sentence-transformers path (primaire)
            self._embedding_mode = "sentence-transformers"
            uncached = [t for t in texts if t not in self._cache]
            if uncached:
                vecs = st.encode(uncached, normalize_embeddings=True, show_progress_bar=False)
                for t, v in zip(uncached, vecs):
                    self._cache[t] = v
            return np.array([self._cache[t] for t in texts])
        else:
            # TF-IDF fallback
            self._embedding_mode = "tfidf"
            if self._tfidf is None:
                raise RuntimeError("TF-IDF non initialisé. Appelez train() d'abord.")
            import scipy.sparse as sp
            if isinstance(self._tfidf, tuple):
                tfidf_word, tfidf_char = self._tfidf
                X_word = tfidf_word.transform(texts)
                X_char = tfidf_char.transform(texts)
                return sp.hstack([X_word, X_char]).toarray()
            return self._tfidf.transform(texts).toarray()

    def train(self, data: list[tuple[str, str, str, str]]):
        """data: liste de (texte, secteur, tech_stack, priorité)"""
        texts      = [d[0] for d in data]
        sectors    = [d[1] for d in data]
        techs      = [d[2] for d in data]
        priorities = [d[3] for d in data]

        # Initialiser TF-IDF si sentence-transformers est indisponible
        st = self._try_load_st()
        if st is None:
            self._embedding_mode = "tfidf"
            logger.info("Mode TF-IDF activé — entraînement du vectoriseur...")
            # Combinaison mot + caractère pour le texte IT français
            # Les mots-clés techniques (COBOL, SAP, banque) sont très distinctifs
            from sklearn.pipeline import FeatureUnion
            from sklearn.base import BaseEstimator, TransformerMixin

            tfidf_word = TfidfVectorizer(
                analyzer="word",
                ngram_range=(1, 3),
                max_features=5000,
                sublinear_tf=True,
                min_df=1,
                token_pattern=r"(?u)\b[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ0-9\-\.]+\b",
            )
            tfidf_char = TfidfVectorizer(
                analyzer="char_wb",
                ngram_range=(3, 5),
                max_features=5000,
                sublinear_tf=True,
                min_df=1,
            )
            from scipy.sparse import hstack
            X_word = tfidf_word.fit_transform(texts)
            X_char = tfidf_char.fit_transform(texts)
            import scipy.sparse as sp
            X_combined = sp.hstack([X_word, X_char]).toarray()
            self._tfidf = (tfidf_word, tfidf_char)
            X = X_combined
            logger.info(f"TF-IDF combiné: matrice {X.shape}")
        else:
            logger.info(f"Embeddings de {len(texts)} exemples...")
            X = self._embed(texts)
            logger.info(f"Embeddings shape: {X.shape}")

        y_sector   = self.sector_le.fit_transform(sectors)
        y_tech     = self.tech_le.fit_transform(techs)
        y_priority = self.priority_le.fit_transform(priorities)

        if self._embedding_mode == "tfidf":
            # LinearSVC est le meilleur classifieur pour les features TF-IDF sparses
            from sklearn.svm import LinearSVC
            from sklearn.calibration import CalibratedClassifierCV

            logger.info("Entraînement classificateur secteur (LinearSVC)...")
            base_sec = LinearSVC(C=3.0, max_iter=5000, random_state=42)
            self.sector_clf = CalibratedClassifierCV(base_sec, cv=3)
            self.sector_clf.fit(X, y_sector)

            logger.info("Entraînement classificateur tech_stack (LinearSVC)...")
            base_tech = LinearSVC(C=2.0, max_iter=5000, random_state=42)
            self.tech_clf = CalibratedClassifierCV(base_tech, cv=3)
            self.tech_clf.fit(X, y_tech)

            logger.info("Entraînement classificateur priorité (LinearSVC)...")
            base_pri = LinearSVC(C=1.0, max_iter=5000, random_state=42)
            self.priority_clf = CalibratedClassifierCV(base_pri, cv=3)
            self.priority_clf.fit(X, y_priority)
        else:
            from sklearn.svm import LinearSVC
            from sklearn.calibration import CalibratedClassifierCV

            logger.info("Entraînement classificateur secteur...")
            base_sec = LinearSVC(C=5.0, max_iter=5000, random_state=42)
            self.sector_clf = CalibratedClassifierCV(base_sec, cv=3)
            self.sector_clf.fit(X, y_sector)

            logger.info("Entraînement classificateur tech_stack...")
            base_tech = LinearSVC(C=5.0, max_iter=5000, random_state=42)
            self.tech_clf = CalibratedClassifierCV(base_tech, cv=3)
            self.tech_clf.fit(X, y_tech)

            logger.info("Entraînement classificateur priorité...")
            base_pri = LinearSVC(C=1.0, class_weight="balanced", max_iter=5000, random_state=42)
            self.priority_clf = CalibratedClassifierCV(base_pri, cv=3)
            self.priority_clf.fit(X, y_priority)

        logger.success(f"Tous les classificateurs entraînés (mode: {self._embedding_mode}).")

    def predict(self, text: str) -> dict:
        if not all([self.sector_clf, self.tech_clf, self.priority_clf]):
            raise RuntimeError("Modèle non entraîné. Appelez train() ou load().")
        x = self._embed([text])

        sector_proba   = self.sector_clf.predict_proba(x)[0]
        tech_proba     = self.tech_clf.predict_proba(x)[0]
        priority_proba = self.priority_clf.predict_proba(x)[0]

        return {
            "sector_label":        self.sector_le.inverse_transform([sector_proba.argmax()])[0],
            "sector_confidence":   float(sector_proba.max()),
            "tech_label":          self.tech_le.inverse_transform([tech_proba.argmax()])[0],
            "tech_confidence":     float(tech_proba.max()),
            "priority_label":      self.priority_le.inverse_transform([priority_proba.argmax()])[0],
            "priority_confidence": float(priority_proba.max()),
            "embedding_mode":      self._embedding_mode,
        }

    def save(self):
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        joblib.dump(self.sector_clf,      MODELS_DIR / "sector_clf.joblib")
        joblib.dump(self.tech_clf,        MODELS_DIR / "tech_clf.joblib")
        joblib.dump(self.priority_clf,    MODELS_DIR / "priority_clf.joblib")
        joblib.dump(self.sector_le,       MODELS_DIR / "sector_le.joblib")
        joblib.dump(self.tech_le,         MODELS_DIR / "tech_le.joblib")
        joblib.dump(self.priority_le,     MODELS_DIR / "priority_le.joblib")
        joblib.dump(self._embedding_mode, MODELS_DIR / "embedding_mode.joblib")
        if self._tfidf is not None:
            if isinstance(self._tfidf, tuple):
                joblib.dump(self._tfidf[0], MODELS_DIR / "tfidf_word.joblib")
                joblib.dump(self._tfidf[1], MODELS_DIR / "tfidf_char.joblib")
            else:
                joblib.dump(self._tfidf, MODELS_DIR / "tfidf.joblib")
        logger.success(f"Modèles sauvegardés dans {MODELS_DIR}")

    def load(self):
        self.sector_clf   = joblib.load(MODELS_DIR / "sector_clf.joblib")
        self.tech_clf     = joblib.load(MODELS_DIR / "tech_clf.joblib")
        self.priority_clf = joblib.load(MODELS_DIR / "priority_clf.joblib")
        self.sector_le    = joblib.load(MODELS_DIR / "sector_le.joblib")
        self.tech_le      = joblib.load(MODELS_DIR / "tech_le.joblib")
        self.priority_le  = joblib.load(MODELS_DIR / "priority_le.joblib")

        mode_file = MODELS_DIR / "embedding_mode.joblib"
        if mode_file.exists():
            self._embedding_mode = joblib.load(mode_file)
        else:
            self._embedding_mode = "sentence-transformers"

        word_file = MODELS_DIR / "tfidf_word.joblib"
        char_file = MODELS_DIR / "tfidf_char.joblib"
        tfidf_file = MODELS_DIR / "tfidf.joblib"
        if word_file.exists() and char_file.exists():
            self._tfidf = (joblib.load(word_file), joblib.load(char_file))
        elif tfidf_file.exists():
            self._tfidf = joblib.load(tfidf_file)

        logger.info(f"Modèles chargés (mode: {self._embedding_mode})")

    def is_ready(self) -> bool:
        return all([self.sector_clf, self.tech_clf, self.priority_clf])
