# LeadGen Francophone 360+ — Contexte projet complet

> Fichier de contexte généré le 2026-05-04 pour Claude.
> Couvre TOUT : plateforme Python + rapport LaTeX.
> Lire ce fichier en début de session pour zero re-explication.

---

## Vue d'ensemble

**Client :** Solvinya Group (ESN COBOL/Mainframe/SAP)
**Objectif :** Automatiser la détection de prospects B2B IT francophones
**Marchés cibles :** France, Belgique, Luxembourg, Suisse, Monaco, Tunisie
**Résultats :** 815 prospects en première exécution, NLP 75% accuracy, LLM 1–3s/message

---

## Arborescence des projets

```
C:/personal/scrapping/
├── leadgen360/              ← Plateforme Python principale
│   ├── api/                 ← FastAPI (8000)
│   ├── automation/          ← LLM message/email generators
│   ├── collectors/          ← Scrapers (LinkedIn, BOAMP, TED, Malt)
│   ├── config/settings.py   ← Pydantic Settings (.env)
│   ├── cookies/             ← Sessions LinkedIn persistées (.jr files)
│   ├── db/                  ← Schema SQL + asyncpg client
│   ├── n8n_workflows/       ← 4 workflows JSON
│   ├── nlp/                 ← TF-IDF + LinearSVC classifier
│   ├── pipeline/            ← Ingest + scorer + enricher
│   ├── tests/               ← 16 pytest (tous passent)
│   ├── docker-compose.yml
│   ├── Makefile
│   ├── pyproject.toml
│   ├── DOCUMENTATION.md     ← Guide technique détaillé (2063 lignes)
│   └── README.md
│
└── rapport_pfe/             ← Rapport LaTeX ESPRIT (47 pages)
    ├── Main.tex             ← Preamble + includes
    ├── Main.pdf             ← PDF compilé (47 pages, ~770 KB)
    ├── Chapter{1-4}.tex
    ├── CONTEXT.md           ← Contexte spécifique LaTeX (bugs, règles)
    └── bibliography.bib
```

---

## Stack technique complète

| Couche | Technologie | Version |
|---|---|---|
| Langage | Python | 3.11 |
| API | FastAPI + Uvicorn | latest |
| DB | PostgreSQL | 15-alpine |
| Driver DB | asyncpg | 0.29 |
| HTTP client | httpx (async) | — |
| LinkedIn | linkedin-api (Tom Quirk) | 2.x |
| Retry | tenacity | — |
| NLP | scikit-learn | 1.4 |
| LLM primaire | Groq (llama-3.1-8b-instant) | — |
| LLM fallback | Ollama (mistral/llama3:8b) | local |
| Automatisation | n8n | 1.x auto-hébergé |
| BI | Metabase OSS | latest |
| Conteneurs | Docker Compose v2 | — |
| Logging | Loguru | — |
| Config | pydantic-settings | — |
| Tests | pytest + pytest-asyncio | — |

---

## Services Docker (docker-compose.yml)

| Conteneur | Image | Port | Rôle |
|---|---|---|---|
| `leadgen_postgres` | postgres:15-alpine | 5432 | DB principale |
| `leadgen_redis` | redis:7-alpine | 6379 | Cache/queue |
| `leadgen_n8n` | n8nio/n8n:latest | 5678 | Workflows automatisés |
| `leadgen_metabase` | metabase/metabase | 3000 | Dashboard BI |
| `leadgen_api` | build local | 8000 | FastAPI REST |

n8n utilise un schéma PostgreSQL dédié (`n8n`), Metabase aussi (`metabase`).

---

## Variables d'environnement (.env)

```bash
# DB
DATABASE_URL=postgresql://leadgen:leadgen_secret@localhost:5432/leadgen360
POSTGRES_USER=leadgen
POSTGRES_PASSWORD=leadgen_secret
POSTGRES_DB=leadgen360

# LinkedIn (jusqu'à 3 comptes pour rotation round-robin)
LINKEDIN_EMAIL_1=...
LINKEDIN_PASSWORD_1=...
LINKEDIN_EMAIL_2=...
LINKEDIN_PASSWORD_2=...

# API auth
API_SECRET_KEY=leadgen360_demo_secret_2024   # header X-API-Key

# LLM
GROQ_API_KEY=...
GROQ_MODEL=llama-3.1-8b-instant
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# NLP
LEADGEN_USE_TFIDF=1   # force TF-IDF sans HuggingFace (recommandé)

# Optionnel
HUNTER_API_KEY=...    # enrichissement email (non implémenté)
COOKIES_DIR=./cookies
N8N_WEBHOOK_URL=http://n8n:5678/webhook
REDIS_URL=redis://localhost:6379/0
```

---

## Commandes make (Makefile)

```bash
make up                  # démarrer tout le stack Docker
make down                # arrêter
make collect             # collecte complète (tous les collecteurs)
make collect-dry         # simulation sans écriture DB
make collect-linkedin    # LinkedIn Jobs seulement (outsourcing_signal)
make collect-linkedin-b2b # LinkedIn B2B direct (RFP/AO/partenariat)
make collect-boamp       # BOAMP seulement
make collect-ted         # TED EU seulement
make train               # entraîner/réentraîner le NLP
make test                # pytest (16 tests)
make demo                # trigger n8n workflow démo via webhook
make status              # santé API + état Docker
make logs                # logs API en temps réel
make db-stats            # stats PostgreSQL par pays/secteur
make rebuild-api         # rebuild image Docker api + restart
make trigger-collect     # POST /api/collect/all via curl
```

---

## Schema base de données (db/init.sql)

### Table `companies`
```sql
id UUID PK | name VARCHAR(255) | linkedin_url VARCHAR(500) UNIQUE
country CHAR(2) | city | sector VARCHAR(80) | description TEXT
technologies TEXT[] | source VARCHAR(50) | raw_data JSONB
company_size_min/max INT | website | created_at | updated_at
```

### Table `opportunities` ← table principale
```sql
id UUID PK | company_id UUID FK→companies
title VARCHAR(500) | description TEXT
opportunity_type VARCHAR(50)  -- voir valeurs ci-dessous
technologies TEXT[] | source_platform VARCHAR(80) | source_url
country CHAR(2) | status VARCHAR(30) DEFAULT 'new'
priority_score SMALLINT  -- 0-100 calculé par scorer_rules
sector_label | tech_label | priority_label | nlp_confidence FLOAT
posted_at | created_at | updated_at
```

**Valeurs `opportunity_type` valides :**
- `outsourcing_signal` — recrutement IT détecté → signal externalisation
- `b2b_rfp` — Request for Proposal direct
- `b2b_tender` — appel d'offres public/privé (BOAMP, TED)
- `b2b_subcontracting` — sous-traitance détectée
- `b2b_partnership` — partenariat/co-traitance

**Valeurs `source_platform` :**
- `linkedin_jobs`, `linkedin_b2b`, `boamp`, `ted`, `malt`

### Table `contacts`
```sql
id UUID PK | company_id UUID FK | full_name | job_title
email | linkedin_url UNIQUE | is_decision_maker BOOL | source
```

### Table `leads`
```sql
id UUID PK | opportunity_id UUID FK | contact_id UUID FK
generated_linkedin_msg TEXT | generated_email TEXT
status VARCHAR(30) DEFAULT 'draft' | sent_at | responded_at | notes
```

---

## Pipeline d'ingestion (pipeline/ingest.py)

6 étapes, ~50ms/prospect :
1. **Normalisation** — country → ISO 2 lettres, tech → taxonomie, sector → fixe
2. **UPSERT entreprise** — `linkedin_url` comme clé unique → retourne `company_id`
3. **Déduplication 30j** — même company_id + même tech + même type dans 30 jours → SKIP
4. **Score règle-métier** — `compute_rule_score(country, sector, tech, boost)` → 0-100
5. **Titre contextuel** — "[Appel d'offres] SAP — Gouvernement LU"
6. **INSERT opportunity** — status='new', priority_score, technologies[]

### Formule de scoring (pipeline/scorer_rules.py)
```
score = country_score × 0.30
      + tech_score    × 0.25
      + sector_score  × 0.25
      + boost/25×100  × 0.20
```

**Scores pays :** LU=100, CH=95, FR=90, BE=85, MC=80, TN=65
**Scores tech :** COBOL=100, Mainframe=100, SAP=85, Java=80, ML=78, Python/DevOps=70
**Scores secteur :** Finance/Banque=100, Finance/Assurance=95, Finance=90

---

## Collecteurs (collectors/)

### 1. LinkedIn Jobs — `linkedin_hiring.py`
- **Signal :** `outsourcing_signal`
- **Logique :** entreprise non-IT qui recrute un dev COBOL/SAP → a un projet actif
- **Boucle :** `for tech in [COBOL, SAP, Java...]: for country in [FR, BE, LU, CH, TN]:`
- **API :** `search_jobs(keywords, location)` → stubs → `get_job(job_id)` → détail
- **Anti-détection :** `sleep(gauss(4.0, 1.5))` entre requêtes
- **Problème connu :** filtre CONTENT ne fonctionne pas → stratégie indirecte

### 2. LinkedIn B2B — `linkedin_b2b.py`
- **Signaux :** `b2b_rfp`, `b2b_tender`, `b2b_subcontracting`, `b2b_partnership`
- **Logique :** recherche d'entreprises acheteuses → scan de leurs publications
- **Patterns regex :** rfp|appel d'offres|recherche prestataire|partenariat…
- **Filtre :** `_ESN_INDICATORS` pour exclure les ESN auto-promotionnels
- **Boost :** RFP=+22, tender=+18, sous-traitance=+16, partenariat=+14

### 3. BOAMP — `boamp.py`
- **API :** `GET boamp-datadila.opendatasoft.com/api/explore/v2.1/records`
- **Filtre :** `?where=objet like "COBOL"&limit=20&order_by=dateparution desc`
- **Signal :** `b2b_tender`
- **15 mots-clés IT** × tous pays francophones

### 4. TED EU — `ted.py`
- **API :** `POST api.ted.europa.eu/v3/notices/search` (POST uniquement ! GET → 405)
- **Query :** `"notice-title=\"SAP\" AND buyer-country=FRA"`
- **Piège :** une seule country par requête → boucle Python sur [FRA, BEL, LUX, CHE]
- **Multilingue :** `buyer.get("fra") or buyer.get("eng")` pour le nom acheteur
- **Codes pays :** ISO alpha-3 (FRA, BEL, LUX, CHE), PAS alpha-2

### 5. Malt — `malt.py`
- **Statut :** INACTIF — protection Cloudflare bloque httpx et Playwright standard
- **Perspective :** Playwright + stealth plugin

### Session Manager — `session_manager.py`
- Pool de 2-3 comptes LinkedIn, rotation round-robin
- Cookies persistés dans `cookies/` au format `.jr` (pickle)
- `initialize()` → async connect, `get_client()` → rotation index

---

## NLP (nlp/)

### Architecture : 2 classifieurs indépendants
- **Classifieur secteur** : TF-IDF word 1-3g (50k features) + char 3-5g (30k) → FeatureUnion → LinearSVC + CalibratedClassifierCV → 10 classes
- **Classifieur priorité** : même pipeline → 3 classes (HIGH/MED/LOW)

### Performances (TF-IDF, corpus 604 exemples)
- CV-5 accuracy secteur : **75.0% ±5.5%** ← seuil atteint
- Test set accuracy secteur : 70.2%
- F1-macro secteur : 68.5%
- Priority accuracy : 85% (test set)
- Latence prédiction : ~100ms

### Variables
```bash
LEADGEN_USE_TFIDF=1   # force TF-IDF (pas de téléchargement HuggingFace)
# Sans ce flag : tente sentence-transformers paraphrase-multilingual-MiniLM-L12-v2
```

### Entraînement
```bash
make train
# ou
LEADGEN_USE_TFIDF=1 python -m nlp.trainer
```
Modèles sauvegardés dans `nlp/models/*.joblib`

---

## API REST FastAPI (api/)

**Base URL :** `http://localhost:8000`
**Auth :** header `X-API-Key: {API_SECRET_KEY}`

| Endpoint | Méthode | Description |
|---|---|---|
| `/health` | GET | Santé API (sans auth) |
| `/api/ingest` | POST | Ingérer un prospect manuel |
| `/api/classify` | POST | Classifier un texte (NLP) |
| `/api/generate/message` | POST | Générer message LinkedIn via LLM |
| `/api/generate/email` | POST | Générer email de prospection |
| `/api/collect/all` | POST | Déclencher collecte complète (background) |
| `/api/collect/linkedin` | POST | Déclencher collecte LinkedIn seule |

`/api/collect/all` retourne immédiatement `{"status":"started"}` — collecte async en BackgroundTasks

---

## LLM / Génération de messages (automation/)

**`llm_client.py`** — client Groq + fallback Ollama
- Groq : llama-3.1-8b-instant, latence 1–3s
- Fallback Ollama local : latence 5–15s si Groq indisponible

**`message_generator.py`** — prompt adapté au type de signal :
- `outsourcing_signal` → "L'entreprise recrute un dev {tech}. Proposer l'externalisation."
- `b2b_tender` → "AO IT détecté. Proposer une réponse complète."
- `b2b_partnership` → "Cherche partenaire. Présenter Solvinya."
- `b2b_rfp` → "RFP publié. Proposer une solution complète."

---

## Workflows n8n (n8n_workflows/)

| Fichier | Nom | Déclencheur | Rôle |
|---|---|---|---|
| `01_linkedin_hiring.json` | LinkedIn Hiring Monitor | Schedule 12h | Collecte LinkedIn Jobs auto |
| `02_boamp_rss.json` | BOAMP RSS | Schedule 6h | Collecte BOAMP auto |
| `03_live_demo.json` | Demo Live | Manuel | Pipeline bout-en-bout (démo soutenance) |
| `04_collect_trigger.json` | Collect Trigger | Schedule 12h + Webhook | Déclenche `/api/collect/all` |

**Workflow 04 (principal en prod) :**
Schedule 12h → POST /api/collect/all → IF status=="started" → OK/ERR
Webhook manuel : `POST localhost:5678/webhook/collect`

**Workflow 03 (démo) :**
Manual → Set params (COBOL/FR) → POST /api/ingest → Wait 3s → GET prospects → Extract opp_id → POST /api/generate/message → Set résultat

---

## Tests (tests/)

16 tests pytest, tous passants :
- `test_api.py` — endpoints health, ingest, classify, generate
- `test_nlp.py` — accuracy CV-5 ≥ 75%
- `test_pipeline.py` — déduplication, scoring unitaire (COBOL/LU = 100)

```bash
make test
# ou
pytest tests/ -v --tb=short
```

---

## Bugs connus & limitations

| Source | Problème | Statut |
|---|---|---|
| Malt.fr | Cloudflare bloque httpx + Playwright | Collecteur inactif |
| LinkedIn | Filtre CONTENT retourne 0 résultats | Contourné (scan publications) |
| TED API | GET retourne 405, POST seulement | Géré dans ted.py |
| TED API | Un pays par requête | Boucle Python |
| asyncpg | Mélange paramètres littéraux/$N | Bug corrigé dans pipeline |

---

## Résultats réels (2 mai 2026, première exécution)

| Source | Pays | Prospects | Score moy. | Type |
|---|---|---|---|---|
| BOAMP | FR | 236 | 66 | b2b_tender |
| TED EU | FR | 145 | 65 | b2b_tender |
| TED EU | BE | 105 | 63 | b2b_tender |
| TED EU | CH | 98 | 65 | b2b_tender |
| TED EU | LU | 74 | 66 | b2b_tender |
| LinkedIn Jobs | FR | 122 | 79 | outsourcing_signal |
| LinkedIn Jobs | BE | 12 | 83 | outsourcing_signal |
| LinkedIn Jobs | TN | 11 | 75 | outsourcing_signal |
| LinkedIn Jobs | LU | 10 | 84 | outsourcing_signal |
| LinkedIn Jobs | CH | 2 | 87 | outsourcing_signal |
| **TOTAL** | | **815** | **≈70** | |

Distribution scores : 0-59 → 270, 60-79 → 387, 80-100 → 158

---

## Rapport LaTeX (rapport_pfe/)

**Fichier principal :** `C:/personal/scrapping/rapport_pfe/Main.tex`
**Output :** `Main.pdf` — 47 pages, compilé avec MiKTeX 24.1

**Compilation :**
```bash
cd C:/personal/scrapping/rapport_pfe
pdflatex -interaction=nonstopmode Main.tex  # × 3 passes
# Si erreur \ar@align@mcell : miktex packages update d'abord
```

**Règles LaTeX critiques** → voir `rapport_pfe/CONTEXT.md` pour le détail complet.
Résumé des pièges principaux :
- Styles TikZ paramétrés `{draw=#1!70}` avec `!` dans l'arg → undefined color
- Style nommé `step` → conflit TikZ built-in → utiliser `pipstep`
- `\\` dans nœud TikZ sans `align=center` → "Not allowed in LR mode"
- `/` dans noms de coordonnées pgfplots → remplacer par `-`
- Espaces avant `{` dans coordonnées pgfplots → mismatch
- Virgules dans argument `tcolorbox[...]` → parsed comme options

---

## Perspectives d'évolution (backlog)

1. **Malt.fr** — Playwright + stealth pour contourner Cloudflare
2. **Enrichissement contacts** — Hunter.io pour email DSI/DRH
3. **Qualification LLM** — pré-qualifier les prospects avant scoring
4. **CRM** — sync HubSpot/Pipedrive via API
5. **Monitoring** — Prometheus + Grafana (volume, latences, taux d'échec)
6. **Multi-tenant** — scoring configurable par client ESN
