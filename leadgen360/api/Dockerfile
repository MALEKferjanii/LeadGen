FROM python:3.11-slim

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copier les dépendances d'abord (cache Docker)
COPY pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        "fastapi>=0.111.0" \
        "uvicorn[standard]>=0.29.0" \
        "asyncpg>=0.29.0" \
        "psycopg2-binary>=2.9.9" \
        "pydantic>=2.7.0" \
        "pydantic-settings>=2.3.0" \
        "python-dotenv>=1.0.1" \
        "linkedin-api>=2.1.1" \
        "httpx>=0.27.0" \
        "tenacity>=8.3.0" \
        "sentence-transformers>=3.0.0" \
        "scikit-learn>=1.5.0" \
        "numpy>=1.26.0" \
        "scipy>=1.13.0" \
        "joblib>=1.4.0" \
        "loguru>=0.7.2" \
        "matplotlib>=3.9.0" \
        "anyio>=4.4.0" \
        "python-jose[cryptography]>=3.3.0" \
        "python-multipart>=0.0.9" \
        "aiofiles>=23.2.1"

# Copier le code source
COPY . .

# Créer le dossier cookies et modèles NLP
RUN mkdir -p /app/cookies /app/nlp/models /app/nlp/reports

# Télécharger le modèle sentence-transformers au build pour éviter le téléchargement au runtime
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')" || true

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
