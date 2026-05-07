# 🚀 LeadGen Francophone 360+

> **Automated B2B Lead Generation Platform for IT Services** — Detects active IT procurement signals across 5 French-speaking countries, classifies them with ML, and generates personalized LinkedIn/email outreach messages using an LLM. Full pipeline runs in under 90 seconds.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111+-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker&logoColor=white)
![n8n](https://img.shields.io/badge/n8n-Automation-EA4B71?style=flat-square&logo=n8n&logoColor=white)
![License](https://img.shields.io/badge/License-Educational-orange?style=flat-square)

---

## 📋 Table of Contents

1. [What This System Does](#-what-this-system-does)
2. [System Architecture](#-system-architecture)
3. [Data Sources & Signal Types](#-data-sources--signal-types)
4. [Full Data Flow](#-full-data-flow)
5. [Technology Stack — With Reasoning](#-technology-stack--with-reasoning)
6. [Module-by-Module Breakdown](#-module-by-module-breakdown)
7. [Database Schema](#-database-schema)
8. [NLP Classification Pipeline](#-nlp-classification-pipeline)
9. [Scoring Formula](#-scoring-formula)
10. [LLM Message Generation](#-llm-message-generation)
11. [n8n Automation Workflows](#-n8n-automation-workflows)
12. [Architecture Decision Records (ADR)](#-architecture-decision-records-adr)
13. [Fresh Installation Guide — From Zero](#-fresh-installation-guide--from-zero)
14. [Usage & Commands](#-usage--commands)
15. [API Reference](#-api-reference)
16. [Compliance & Ethics](#-compliance--ethics)

---

## 🎯 What This System Does

**LeadGen 360+** is a fully automated lead generation pipeline built for **Solvinya Group**, a French IT services company (ESN — Entreprise de Services du Numérique). Its job is to automatically find companies that are likely to need external IT expertise.

### The Business Problem

Solvinya Group sells IT services: outsourcing, custom dev, consulting. Their salespeople manually searched LinkedIn, government tender platforms, and freelance marketplaces every day for companies that:
- Are recruiting IT developers internally (→ may prefer outsourcing instead)
- Published RFPs or public procurement notices
- Posted about technology needs on social media

This manual process was slow, incomplete, and inconsistent.

### The Solution: 5-Step Automated Pipeline

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   COLLECT   │───▶│  NORMALIZE  │───▶│    SCORE    │───▶│  CLASSIFY   │───▶│   GENERATE  │
│  (5 sources)│    │ (deduplicate│    │  (0-100 rule│    │  (NLP: ML   │    │  (LLM: write│
│             │    │  + upsert)  │    │  formula)   │    │  + sector)  │    │  outreach)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                                                                             │
       ▼                                                                             ▼
  Raw signals                                                              LinkedIn message
  from web                                                                 + email draft
```

**Target markets:** France 🇫🇷 · Belgium 🇧🇪 · Luxembourg 🇱🇺 · Switzerland 🇨🇭 · Tunisia 🇹🇳

---

## 🏗️ System Architecture

The platform is composed of **5 Docker services** that communicate through PostgreSQL and HTTP calls:

```mermaid
graph TB
    subgraph EXTERNAL["🌐 External Data Sources"]
        LI["💼 LinkedIn\nJobs API"]
        LIB["📢 LinkedIn\nCompany Posts"]
        BOAMP["🏛️ BOAMP\nFrance Gov Tenders"]
        TED["🇪🇺 TED EU\nPublic Tenders"]
        MALT["👨‍💻 Malt.fr\nFreelance Market"]
    end

    subgraph DOCKER["🐳 Docker Compose Stack"]
        subgraph API["⚡ FastAPI :8000"]
            COLLECT["POST /api/collect"]
            INGEST["POST /api/ingest"]
            CLASSIFY["POST /api/classify"]
            GENERATE["POST /api/generate/message"]
            HEALTH["GET /health"]
        end

        subgraph NLP["🧠 NLP Engine"]
            EMB["SentenceTransformers\nparaphrase-multilingual\nMiniLM-L12-v2 (384-dim)"]
            LR["LogisticRegression\n3 classifiers\n(sector / tech / priority)"]
        end

        subgraph LLM["🤖 LLM Engine"]
            GROQ["Groq API\nllama-3.1-8b-instant"]
            OLLAMA["Ollama Fallback\nmistral (local)"]
        end

        subgraph DB["🗄️ PostgreSQL 15 :5432"]
            COMP["companies"]
            OPP["opportunities"]
            CONT["contacts"]
            LEAD["leads"]
        end

        N8N["⚙️ n8n :5678\n4 Automation Workflows"]
        META["📊 Metabase :3000\nDashboards & KPIs"]
        REDIS["⚡ Redis :6379\nCache & Queue"]
    end

    LI --> COLLECT
    LIB --> COLLECT
    BOAMP --> INGEST
    TED --> INGEST
    MALT --> COLLECT

    COLLECT --> INGEST
    INGEST --> DB
    INGEST --> CLASSIFY
    CLASSIFY --> EMB --> LR --> OPP
    GENERATE --> GROQ
    GROQ -->|"fallback"| OLLAMA
    GENERATE --> LEAD

    N8N -->|"HTTP triggers"| API
    META -->|"JDBC"| DB
    API --> REDIS
```

### Service Map

| Service | Port | Role |
|---------|------|------|
| **FastAPI** | `8000` | REST API — orchestrates all pipeline steps |
| **PostgreSQL 15** | `5432` | Central database — stores all data |
| **Redis 7** | `6379` | Session cache, future job queue |
| **n8n** | `5678` | Visual workflow automation (cron + webhooks) |
| **Metabase** | `3000` | Business intelligence dashboards |

---

## 📡 Data Sources & Signal Types

The system monitors **5 sources** for **5 types of procurement signals**:

```mermaid
graph LR
    subgraph SOURCES["Data Sources"]
        A["💼 LinkedIn Jobs"]
        B["📢 LinkedIn Posts"]
        C["🏛️ BOAMP"]
        D["🇪🇺 TED EU"]
        E["👨‍💻 Malt.fr"]
    end

    subgraph SIGNALS["Signal Types"]
        S1["🔄 outsourcing_signal\n(IT hiring → will outsource)"]
        S2["📋 b2b_rfp\n(Request For Proposal)"]
        S3["📑 b2b_tender\n(Public Procurement)"]
        S4["🤝 b2b_subcontracting\n(Subcontracting needed)"]
        S5["🔗 b2b_partnership\n(Tech partnership)"]
    end

    A -->|"Non-IT company recruits\nIT dev = outsourcing signal"| S1
    B -->|"Company post contains\nRFP keywords"| S2
    B -->|"Post contains\nsubcontracting keywords"| S4
    B -->|"Post contains\npartnership keywords"| S5
    C -->|"French public tender\nopen data API"| S3
    D -->|"EU public tender\nfor 4 countries"| S3
    E -->|"Freelance project\nbriefs"| S3
```

### Why Each Source?

| Source | Why It Was Chosen | Volume/Run | Anti-Detection |
|--------|-------------------|------------|----------------|
| **LinkedIn Jobs** | A non-IT company hiring 3+ Java devs signals they may prefer IT outsourcing instead | ~30 per tech searched | Gaussian delay, cookie auth, 3-account rotation |
| **LinkedIn B2B Posts** | Companies publicly announce RFPs and subcontracting needs | ~50–100 | Same as above |
| **BOAMP** | Official French government tender open data — no auth required, structured JSON | ~215–236/week | None needed |
| **TED EU** | Covers Belgium, Luxembourg, Switzerland — same signal type | ~30–50 | Standard retry |
| **Malt.fr** | Freelance missions = companies with short-term tech needs | ~10–20 | CloudFlare bypass needed |

---

## 🔄 Full Data Flow

This diagram traces a single signal from raw web data to a ready-to-send LinkedIn message:

```mermaid
flowchart TD
    A["🌐 Web Source\n(e.g. LinkedIn Jobs)"] --> B["collectors/linkedin_hiring.py\nFetch job postings"]
    B --> C{"Is company\nnon-IT sector?"}
    C -->|"No → skip"| Z1["❌ Filtered out"]
    C -->|"Yes → outsourcing signal"| D["Raw dict:\n{company, tech, country, type}"]
    D --> E["pipeline/ingest.py\nnormalize()"]
    E --> F["db/queries/companies.py\nUPSERT by linkedin_url"]
    F --> G{"Duplicate check:\nsame company + tech\nin last 30 days?"}
    G -->|"Yes → skip"| Z2["❌ Already tracked"]
    G -->|"No"| H["pipeline/scorer_rules.py\nrule_score = country×0.30\n+ tech×0.25 + sector×0.25\n+ boost×0.20"]
    H --> I["db/queries/opportunities.py\nINSERT opportunity\nstatus='new'"]
    I --> J["POST /api/classify\nnlp/classifier.py"]
    J --> K["SentenceTransformers\nEncode text → 384-dim vector"]
    K --> L["3× LogisticRegression\n→ sector_label\n→ tech_label\n→ priority_label"]
    L --> M["UPDATE opportunities SET\nsector_label, tech_label,\npriority_label, nlp_confidence"]
    M --> N["POST /api/generate/message"]
    N --> O["Groq API\nllama-3.1-8b-instant"]
    O --> P["INSERT INTO leads\n(linkedin_msg, email_draft)"]
    P --> Q["✅ Lead ready\nin Metabase dashboard"]

    style A fill:#4A90D9,color:#fff
    style Q fill:#27AE60,color:#fff
    style Z1 fill:#E74C3C,color:#fff
    style Z2 fill:#E74C3C,color:#fff
    style H fill:#F39C12,color:#fff
    style L fill:#9B59B6,color:#fff
    style O fill:#1ABC9C,color:#fff
```

---

## 🛠️ Technology Stack — With Reasoning

Every technology choice was made deliberately. Here is what was chosen and **why**:

### Core Language: Python 3.11

**Why Python and not Node.js/Go?**
- The ML/NLP ecosystem (scikit-learn, sentence-transformers, joblib) only exists properly in Python
- asyncio + asyncpg gives competitive async performance
- LinkedIn's unofficial API library (`linkedin-api`) is Python-only
- Groq and Ollama SDKs are Python-first

### Web Framework: FastAPI

**Why FastAPI and not Flask/Django?**
- Native `async/await` — critical for non-blocking HTTP calls to LinkedIn/BOAMP/Groq simultaneously
- Automatic OpenAPI/Swagger docs at `/docs` — zero extra work for API documentation
- Pydantic v2 models for request/response validation (type safety from day 1)
- Lifespan events for loading the NLP model once at startup (not per-request)

### Database: PostgreSQL 15

**Why PostgreSQL and not MongoDB or SQLite?**

```
SQLite    → Not concurrent, no JSON queries, no real-time analytics
MongoDB   → No JOIN support (leads → opportunities → companies chain), no Metabase native support
PostgreSQL → JSONB for raw_data, TEXT[] for technologies array, UUID native, asyncpg driver
```

- `TEXT[]` native array type stores `technologies: ["COBOL", "SAP"]` without a join table
- `JSONB` stores the full raw API response for debugging without a fixed schema
- `UPDATE triggers` auto-set `updated_at = NOW()` on every update (no ORM overhead)
- Native JDBC connector in Metabase (zero config)

### NLP Stack: SentenceTransformers + LogisticRegression

**Why not fine-tune BERT or use GPT-4 for classification?**

```mermaid
graph LR
    subgraph OUR["✅ Our Approach (Chosen)"]
        A["paraphrase-multilingual\nMiniLM-L12-v2\n(pre-trained, 384-dim)"]
        B["LogisticRegression\n(3 classifiers)"]
        A --> B
    end

    subgraph ALT1["❌ Fine-tuned BERT"]
        C["Need 5000+ labeled examples\nGPU required\n440MB+ model size"]
    end

    subgraph ALT2["❌ GPT-4 Classification"]
        D["$0.03/1000 tokens\nNo offline use\nNo training data ownership"]
    end

    style OUR fill:#27AE60,color:#fff
    style ALT1 fill:#E74C3C,color:#fff
    style ALT2 fill:#E74C3C,color:#fff
```

| Criterion | Our Choice | Fine-tuned BERT | GPT-4 API |
|-----------|-----------|----------------|----------|
| Training data needed | 300 examples | 5,000+ examples | 0 (but no control) |
| Training time | ~30s on CPU | 2–4h on GPU | N/A |
| Model size | 45 MB `.joblib` | 440 MB minimum | Cloud dependency |
| Multilingual | ✅ Native (FR, EN, DE...) | ❌ One language per model | ✅ |
| Explainability | ✅ LR coefficients | ❌ Black box | ❌ Black box |
| Cost | $0 | GPU cost | Per-token billing |
| Offline capability | ✅ Fully local | ✅ After training | ❌ Always online |

The `paraphrase-multilingual-MiniLM-L12-v2` model was specifically designed to encode French (and 50+ other languages) into a shared 384-dimensional embedding space — perfect for classifying French procurement texts.

### LLM: Groq API (with Ollama fallback)

**Why Groq and not OpenAI GPT-4?**
- Groq provides `llama-3.1-8b-instant` at **100× the speed** of GPT-4 via custom LPU hardware
- Free tier is sufficient for demo volumes
- **Ollama fallback** means zero downtime if Groq is unreachable — the system spins up `mistral` locally

### Workflow Automation: n8n

**Why n8n and not Airflow/Celery?**
- Airflow requires a DAG Python file per workflow + separate scheduler + worker processes
- n8n runs in the same Docker Compose and has a visual editor (great for demos and non-developer colleagues)
- Built-in webhook triggers, cron scheduling, HTTP nodes — no custom code needed for orchestration
- Can embed workflow execution directly into a Metabase iframe

### Dashboard: Metabase

**Why Metabase and not Power BI or Grafana?**

| Criterion | Metabase | Power BI | Grafana |
|-----------|----------|----------|---------|
| Deployment | Docker 1-liner | Windows + Pro license | Docker |
| PostgreSQL | Native JDBC | Requires Data Gateway | Native |
| Cost | Free | 10€/user/month | Free |
| SQL queries | Visual + raw SQL | DAX (proprietary) | PromQL focused |
| Embeddable | iframe natively | Premium API | Native |
| Target users | Business users | BI analysts | DevOps/SRE |

Metabase sits inside the same `docker-compose.yml` as everything else — no extra infrastructure, no extra credentials, no Azure tenant needed.

---

## 📁 Module-by-Module Breakdown

### Complete Project Structure

```
leadgen360/
│
├── 📡 api/                        FastAPI REST service (port 8000)
│   ├── main.py                    App init + lifespan (load NLP at startup)
│   ├── auth.py                    X-API-Key validation middleware
│   ├── Dockerfile                 Python 3.11-slim image
│   └── routes/
│       ├── health.py              GET /health (DB + NLP status check)
│       ├── ingest.py              POST /api/ingest (batch prospect insert)
│       ├── classify.py            POST /api/classify (run NLP classifiers)
│       ├── generate.py            POST /api/generate/message (LLM outreach)
│       └── collect.py             POST /api/collect/* (trigger scrapers)
│
├── 🕷️ collectors/                  Web scraping modules
│   ├── base.py                    Abstract BaseCollector (interface contract)
│   ├── linkedin_hiring.py         LinkedIn Jobs → outsourcing signals
│   ├── linkedin_b2b.py            LinkedIn company posts → B2B signals
│   ├── linkedin_client.py         linkedin-api wrapper + cookie persistence
│   ├── boamp.py                   French public tender open data API
│   ├── ted.py                     EU public tender API (BE, LU, CH)
│   ├── malt.py                    Malt.fr freelance marketplace
│   ├── session_manager.py         LinkedIn account pool (3 accounts max)
│   └── run_all.py                 CLI orchestrator with argparse
│
├── 🗄️ db/                          Database layer
│   ├── client.py                  asyncpg connection pool (min=2, max=10)
│   ├── init.sql                   PostgreSQL schema (4 tables + triggers)
│   └── queries/
│       ├── companies.py           INSERT / UPSERT company records
│       ├── contacts.py            Contact management
│       ├── opportunities.py       Opportunity CRUD + NLP label updates
│       └── leads.py               Lead record creation
│
├── ⚙️ pipeline/                    Data processing
│   ├── ingest.py                  normalize → upsert → deduplicate → score → insert
│   ├── scorer_rules.py            Deterministic score formula (0–100)
│   └── enricher.py                Future Hunter.io email enrichment
│
├── 🧠 nlp/                         Machine learning classification
│   ├── classifier.py              SentenceTransformers + LogisticRegression (3 models)
│   ├── trainer.py                 make train entry point
│   ├── evaluator.py               5-fold cross-val + confusion matrices
│   ├── scorer.py                  Fuses rule score + NLP predictions
│   ├── data/training_data.py      300+ hand-annotated French examples
│   ├── models/                    Serialized .joblib model files
│   │   ├── priority_clf.joblib
│   │   ├── sector_clf.joblib
│   │   ├── tech_clf.joblib
│   │   ├── tfidf.joblib
│   │   └── embedding_mode.joblib
│   └── reports/                   Evaluation outputs (PNG + JSON)
│
├── 🤖 automation/                  LLM-powered message generation
│   ├── llm_client.py              Groq API + Ollama fallback
│   ├── message_generator.py       LinkedIn message prompt templates
│   └── email_generator.py         Email generation
│
├── ⚙️ config/
│   └── settings.py                Pydantic BaseSettings (.env → typed config)
│
├── 🔧 n8n_workflows/               n8n JSON workflow definitions
│   ├── 01_linkedin_hiring.json    Hourly LinkedIn job collection
│   ├── 02_boamp_rss.json          BOAMP RSS polling
│   ├── 03_live_demo.json          90-second soutenance demo
│   └── 04_collect_trigger.json    Manual collection webhook
│
├── 🧪 tests/                       pytest test suite
│   ├── conftest.py                Shared fixtures
│   ├── test_api.py                Route tests (httpx TestClient)
│   ├── test_nlp.py                Classifier accuracy tests
│   └── test_pipeline.py           Ingestion logic tests
│
├── 🐳 docker-compose.yml           5 services definition
├── 📦 pyproject.toml               Python dependencies (Poetry)
├── 🔐 .env.example                 Credentials template
└── 🍪 cookies/                     LinkedIn session cookies (gitignored)
```

---

## 🗄️ Database Schema

Four tables form a simple relational hierarchy: **company → opportunity → contact → lead**

```mermaid
erDiagram
    companies {
        UUID id PK
        VARCHAR name
        VARCHAR linkedin_url UK
        VARCHAR website
        CHAR(2) country
        VARCHAR sector
        TEXT[] technologies
        VARCHAR source
        JSONB raw_data
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    opportunities {
        UUID id PK
        UUID company_id FK
        VARCHAR title
        VARCHAR opportunity_type
        TEXT[] technologies
        SMALLINT priority_score
        VARCHAR sector_label
        VARCHAR tech_label
        VARCHAR priority_label
        FLOAT nlp_confidence
        VARCHAR source_platform
        CHAR(2) country
        VARCHAR status
        TIMESTAMPTZ posted_at
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    contacts {
        UUID id PK
        UUID company_id FK
        VARCHAR full_name
        VARCHAR job_title
        VARCHAR email
        VARCHAR linkedin_url UK
        BOOLEAN is_decision_maker
        TIMESTAMPTZ created_at
    }

    leads {
        UUID id PK
        UUID opportunity_id FK
        UUID contact_id FK
        TEXT generated_linkedin_msg
        TEXT generated_email
        VARCHAR status
        TIMESTAMPTZ sent_at
        TIMESTAMPTZ responded_at
        TEXT notes
        TIMESTAMPTZ created_at
    }

    companies ||--o{ opportunities : "has"
    companies ||--o{ contacts : "has"
    opportunities ||--o{ leads : "generates"
    contacts ||--o{ leads : "targeted by"
```

### Key Design Decisions

**Why `TEXT[]` for technologies?**
A company can be looking for `["COBOL", "SAP", "Java"]` simultaneously. A join table would require 3× more queries to insert and read. PostgreSQL's native array type handles this in a single column, and `= ANY(technologies)` works in WHERE clauses for deduplication.

**Why `JSONB raw_data` in companies?**
Each collector returns slightly different JSON. JSONB allows storing the raw API response for debugging without defining a fixed schema per source. This is schema-on-read: the normalized fields are extracted into proper columns, but nothing is lost.

**Why UUID instead of SERIAL?**
UUIDs are generated by PostgreSQL (`gen_random_uuid()`) and safe to use in distributed or multi-instance setups. There is no risk of ID collision if two collector instances run simultaneously.

**Auto-updated `updated_at` trigger:**
```sql
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```
Every table with `updated_at` fires this trigger on UPDATE — no ORM or application-level timestamp management needed.

### Performance Indexes

```sql
CREATE INDEX idx_opp_country  ON opportunities(country);
CREATE INDEX idx_opp_sector   ON opportunities(sector_label);
CREATE INDEX idx_opp_score    ON opportunities(priority_score DESC);
CREATE INDEX idx_opp_status   ON opportunities(status);
CREATE INDEX idx_opp_created  ON opportunities(created_at DESC);
```

These indexes target Metabase's most common GROUP BY queries: "top opportunities by score", "count by country", "filter by status".

---

## 🧠 NLP Classification Pipeline

The NLP system runs **3 parallel classifiers** on every opportunity's text:

```mermaid
flowchart TD
    INPUT["📄 Raw text:\n'Banque Populaire recrute\n3 développeurs COBOL\npour mainframe Paris'"]

    INPUT --> ENCODE["🔢 SentenceTransformers\nparaphrase-multilingual-MiniLM-L12-v2\n\nEncode text → 384-dimensional vector"]

    ENCODE --> C1["🏢 sector_clf\nLogisticRegression\n12 classes\n\n→ Finance/Banque (92%)"]
    ENCODE --> C2["💻 tech_clf\nLogisticRegression\n10 classes\n\n→ COBOL (87%)"]
    ENCODE --> C3["📈 priority_clf\nLogisticRegression\n3 classes\n\n→ high (81%)"]

    C1 --> OUT["📊 Classification Result\nsector_label: Finance/Banque\ntech_label: COBOL\npriority_label: high\nnlp_confidence: 0.87\nnlp_score: 85"]
    C2 --> OUT
    C3 --> OUT

    OUT --> DB["🗄️ UPDATE opportunities\nSET sector_label, tech_label,\npriority_label, nlp_confidence"]

    style INPUT fill:#3498DB,color:#fff
    style ENCODE fill:#9B59B6,color:#fff
    style C1 fill:#E67E22,color:#fff
    style C2 fill:#E67E22,color:#fff
    style C3 fill:#E67E22,color:#fff
    style OUT fill:#27AE60,color:#fff
    style DB fill:#2C3E50,color:#fff
```

### Sector Labels (12 classes)

| Label | Example Signal |
|-------|---------------|
| `Finance/Banque` | "Banque recrute développeur COBOL" |
| `Finance/Assurance` | "AXA cherche expert Mainframe" |
| `Tech` | "Startup SaaS recherche CTO" |
| `Tech/IA` | "Machine Learning Engineer for NLP" |
| `Industrie/RH` | "Groupe industriel externalise RH" |
| `Secteur public` | "Appel d'offres ministère numérique" |
| `Santé` | "CHU recherche prestataire DSI" |
| `Energie` | "EDF soustraite développement Java" |
| `Transport` | "SNCF appel d'offres infra IT" |
| `Retail` | "Enseigne retail cherche SAP MM" |
| `Telecom` | "Opérateur migration réseau" |
| `Autre` | Default fallback |

### Technology Labels (10 classes)

```
COBOL          (100 score) — Legacy banking systems, rarest skill
Mainframe      (100 score) — IBM z/OS environments
SAP            ( 85 score) — ERP systems
Java           ( 80 score) — Enterprise backends
Data Engineer  ( 78 score) — Data pipeline specialists
Machine Learning( 75 score) — AI/ML projects
Python         ( 70 score) — Data science, scripting
DevOps         ( 70 score) — CI/CD, cloud infra
Salesforce     ( 65 score) — CRM implementations
React          ( 55 score) — Frontend development
```

### Training Data

- **300+ annotated examples** in `nlp/data/training_data.py`
- All in French, covering real procurement language
- Format: `(text, sector_label, tech_label, priority_label)`
- Evaluation: **5-fold cross-validation**, target ≥ 75% accuracy

### TF-IDF Fallback

If SentenceTransformers download fails (no internet, timeout):
```bash
LEADGEN_USE_TFIDF=1  # set in .env
```
This activates `TfidfVectorizer` with character + word n-grams (1–3). Same LogisticRegression downstream. About 10% less accurate but runs offline with no downloaded model.

---

## 📊 Scoring Formula

Every opportunity gets a **priority score from 0 to 100** computed in two phases:

### Phase 1: Rule-Based Score (deterministic)

```
score = (country_score  × 0.30)
      + (tech_score     × 0.25)
      + (sector_score   × 0.25)
      + (priority_boost × 0.20)
```

**Country weights** (based on IT outsourcing market density):

```
🇱🇺 Luxembourg : 100   (highest finance/IT density per capita)
🇨🇭 Switzerland: 95    (banking + pharma sectors)
🇫🇷 France     : 90    (primary market + largest volume)
🇧🇪 Belgium    : 85    (EU institutions + finance)
🇲🇨 Monaco     : 80    (high-value clients)
🇹🇳 Tunisia    : 65    (emerging nearshore market)
   Default    : 50
```

**Technology weights** (based on Solvinya's specializations and market rarity):

```
COBOL, Mainframe : 100  (critical legacy, almost no talent pool)
SAP              :  85  (complex ERP, high day rates)
Java             :  80  (enterprise mainstream)
Data Engineer    :  78  (high demand, data lakes)
Machine Learning :  75  (AI adoption wave)
Python           :  70  (data science)
DevOps           :  70  (cloud migration)
Salesforce       :  65  (CRM ecosystem)
React            :  55  (frontend, lower margin)
```

**Priority boost** — collector-set integer (0–25) that pushes scores above threshold:
- LinkedIn COBOL job post in Luxembourg: boost = 25 → score reaches 100

### Phase 2: NLP Fusion Score

After classification, the NLP confidence modulates the final score:
```python
final_score = rule_score * 0.60 + (nlp_confidence * 100) * 0.40
```

**Example calculation:**

| Component | Value | Weight | Points |
|-----------|-------|--------|--------|
| Country (Luxembourg) | 100 | 30% | 30 |
| Technology (COBOL) | 100 | 25% | 25 |
| Sector (Finance/Banque) | 100 | 25% | 25 |
| Priority boost (25→100) | 100 | 20% | 20 |
| **Rule score** | | | **100** |
| NLP confidence | 0.87 | 40% fusion | → **95** |

---

## 🤖 LLM Message Generation

When a salesperson requests a message for a high-scoring opportunity, the system calls Groq with a structured French-language prompt:

```mermaid
sequenceDiagram
    participant S as Salesperson / n8n
    participant A as FastAPI /api/generate/message
    participant G as Groq API (llama-3.1-8b)
    participant O as Ollama (fallback)
    participant D as PostgreSQL

    S->>A: POST {opportunity_id, contact_id}
    A->>D: SELECT opportunity + company details
    D-->>A: {company_name, sector, tech, country, signal_type}
    A->>G: POST prompt (French, structured)
    alt Groq available
        G-->>A: LinkedIn message (5 lines max)
    else Groq unavailable
        A->>O: POST same prompt
        O-->>A: LinkedIn message (local LLM)
    end
    A->>D: INSERT INTO leads (linkedin_msg, email)
    A-->>S: {lead_id, linkedin_message, email_draft}
```

### Prompt Design

The prompt enforces strict rules to avoid generic sales copy:
```
Tu es business developer senior chez Solvinya Group, ESN spécialisée en IA et développement.
Rédige un message LinkedIn de prospection en français pour ce prospect :

- Entreprise : {company_name}
- Secteur : {sector}
- Technologie détectée : {technology}
- Pays : {country}
- Signal : cette entreprise recrute activement des profils {technology}

Règles STRICTES :
- Maximum 5 lignes
- Ton professionnel mais direct, pas vendeur
- Mentionner le signal spécifique (l'offre d'emploi ou l'appel d'offres)
- Terminer par une question ouverte sur leur stratégie
- NE PAS utiliser de formules génériques ("Je me permets de...")
```

**Why these constraints?** LinkedIn's algorithm deprioritizes generic outreach. Short, specific messages referencing a real signal (e.g., "I noticed you're hiring 3 COBOL developers") get 3–5× higher response rates than boilerplate.

---

## ⚙️ n8n Automation Workflows

Four workflows automate the collection and demo:

```mermaid
gantt
    title n8n Workflow Schedule
    dateFormat HH:mm
    axisFormat %H:%M

    section Daily Automation
    01 LinkedIn Jobs Collect     :active, 00:00, 24h
    02 BOAMP RSS Poll            :active, 00:00, 24h

    section Manual Triggers
    03 Live Demo (Soutenance)    :crit, 00:00, 1m
    04 Manual Collection         :00:00, 1m
```

### Workflow 01 — LinkedIn Jobs (Hourly)
```
⏰ Cron (every hour)
    → POST /api/collect/linkedin
    → Logs result count
```

### Workflow 02 — BOAMP RSS Feed
```
📡 RSS Poll (BOAMP feed URL)
    → Parse new tender entries
    → POST /api/ingest (batch)
    → Filter by technology keywords
```

### Workflow 03 — Live Demo (Soutenance 90s)
```
▶️ Manual Execute button
    → POST /api/ingest  (inject test prospect)
    → Wait 3 seconds
    → GET /api/prospects?score=70  (fetch top results)
    → POST /api/generate/message  (generate LinkedIn message)
    → Display result in n8n node output
```

### Workflow 04 — Manual Collection Trigger
```
🌐 Webhook (POST /webhook/collect)
    → POST /api/collect/all
    → Return collection summary
```

---

## 📐 Architecture Decision Records (ADR)

### ADR-1: linkedin-api over Selenium

**Context:** The system needs to search LinkedIn for job postings and company posts at scale.

**Decision:** Use the unofficial `linkedin-api` Python library (cookie-based auth) instead of browser automation.

| Criterion | `linkedin-api` ✅ | Selenium ❌ |
|-----------|------------------|------------|
| Detection risk | Uses internal mobile API endpoints | Browser user-agent, easily fingerprinted |
| Speed | ~0.3s/request | ~3s/request (10× slower) |
| Infrastructure | No headless browser needed | Chrome + chromedriver + memory |
| Cookie persistence | Saved to disk, survives restart | Lost on process exit |
| Maintenance | Maintained library + cookie auth | Chrome version lock-in |

**Consequences:**
- Cookie files must be managed in `cookies/` directory (gitignored)
- LinkedIn may issue `CHALLENGE_REQUIRED` (manual re-login needed ~monthly)
- Account pool of 3 accounts (750 req/day total, 250 each) mitigates rate limiting
- Gaussian delay `random.gauss(4.0, 1.5)` between requests prevents detection

---

### ADR-2: SentenceTransformers + LogisticRegression over fine-tuned BERT

**Context:** Need to classify French procurement texts into 12 sectors, 10 technologies, 3 priority levels.

**Decision:** Use pre-trained multilingual embeddings + lightweight classifier.

| Criterion | SentenceTransformers + LR ✅ | Fine-tuned BERT ❌ |
|-----------|---------------------------|------------------|
| Training data | 300 examples sufficient | 5,000+ required |
| Training time | ~30s on CPU | 2–4h on GPU |
| Model file size | 45 MB (`.joblib`) | 440 MB minimum |
| Expected F1 | ~85% macro | ~92% (unjustifiable without more data) |
| Explainability | LR coefficients readable | Black box |
| Languages | 50+ languages natively | Fine-tune per language |
| Offline | ✅ After first download | ✅ After training |

**Consequences:**
- `paraphrase-multilingual-MiniLM-L12-v2` downloaded once (45 MB) at container build time
- TF-IDF fallback for fully offline environments (`LEADGEN_USE_TFIDF=1`)
- Accuracy target ≥ 75% CV F1 — run `python -m nlp.trainer` to verify

---

### ADR-3: Metabase over Power BI

**Context:** Need a dashboard for the soutenance (academic defense) that can be set up in minutes.

**Decision:** Use Metabase Community Edition in Docker.

| Criterion | Metabase ✅ | Power BI ❌ |
|-----------|-----------|-----------|
| Deployment | `docker-compose up` (same stack) | Windows installer + Power BI Desktop |
| PostgreSQL | Native JDBC, zero config | Requires Power BI Gateway |
| Cost | Free (Community) | 10€/user/month (Pro) |
| Public sharing | Shareable link (no account needed) | Requires Azure AD tenant |
| Iframe embed | Native (used in n8n UI) | Premium API only |
| Target audience | Any user with a browser | BI professionals |

**Consequences:**
- Metabase stores its own schema in a separate `metabase.*` PostgreSQL schema
- First-run setup wizard takes ~3 minutes (one-time)
- Dashboards are portable via JSON export

---

## 🖥️ Fresh Installation Guide — From Zero

This guide assumes a **brand new Windows/Linux/Mac machine** with nothing installed.

### Prerequisites Checklist

```
□ Docker Desktop (or Docker Engine on Linux)
□ Python 3.11+
□ Git
□ A Groq API key (free at console.groq.com)
□ 1–3 LinkedIn accounts (email + password)
□ 8 GB RAM minimum (Metabase + PostgreSQL + API)
□ 10 GB free disk space (Docker images + ML model)
```

---

### Step 1: Install Docker

**Windows:**
1. Go to https://www.docker.com/products/docker-desktop
2. Download "Docker Desktop for Windows"
3. Run the installer — requires WSL2 backend (installer will prompt)
4. Restart your computer
5. Open Docker Desktop and wait for the green "Running" status

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

**Mac:**
```bash
brew install --cask docker
# Then open Docker.app and wait for startup
```

**Verify:**
```bash
docker --version       # Docker version 24+
docker compose version # Docker Compose version 2+
```

---

### Step 2: Install Python 3.11

**Windows:**
1. Go to https://www.python.org/downloads/
2. Download Python 3.11.x (not 3.12+ — sentence-transformers may lag)
3. Run installer → ✅ check "Add Python to PATH"
4. Verify:
```powershell
python --version   # Python 3.11.x
pip --version
```

**Linux:**
```bash
sudo apt update && sudo apt install python3.11 python3.11-pip python3.11-venv -y
```

**Mac:**
```bash
brew install python@3.11
```

---

### Step 3: Clone the Repository

```bash
git clone <your-repo-url> leadgen360
cd leadgen360
```

If no git remote exists yet, simply copy the project folder:
```bash
# Windows PowerShell
Copy-Item -Recurse C:\personal\scrapping\leadgen360 . -Force

# Linux/Mac
cp -r /path/to/leadgen360 . && cd leadgen360
```

---

### Step 4: Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in:

```bash
# ─── PostgreSQL ───────────────────────────────────────────
POSTGRES_USER=leadgen
POSTGRES_PASSWORD=leadgen_secret_2024
POSTGRES_DB=leadgen360
DATABASE_URL=postgresql://leadgen:leadgen_secret_2024@postgres:5432/leadgen360

# ─── LinkedIn accounts (minimum 1, maximum 3) ─────────────
LINKEDIN_EMAIL_1=your.email@gmail.com
LINKEDIN_PASSWORD_1=your_linkedin_password

# Optional: 2nd and 3rd account for rate limit rotation
LINKEDIN_EMAIL_2=second.email@gmail.com
LINKEDIN_PASSWORD_2=second_password

# ─── Groq API (free) ──────────────────────────────────────
# Get your key at: https://console.groq.com/keys
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=llama-3.1-8b-instant

# ─── Ollama (optional, local LLM fallback) ────────────────
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# ─── Hunter.io (optional, email enrichment) ───────────────
HUNTER_API_KEY=

# ─── n8n ──────────────────────────────────────────────────
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin123

# ─── Redis ────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ─── API Security ─────────────────────────────────────────
API_KEY=my-secret-api-key-change-this
```

> ⚠️ **Never commit `.env` to git.** It contains your LinkedIn passwords and API keys.

---

### Step 5: Create Python Virtual Environment

```bash
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/Mac
python3.11 -m venv .venv
source .venv/bin/activate
```

Install dependencies:
```bash
pip install -e ".[dev]"
# or with pip directly:
pip install -r requirements.txt
```

> The first install downloads `sentence-transformers` and its dependencies (~500 MB total including PyTorch). This takes 2–5 minutes on a good connection.

---

### Step 6: Start All Docker Services

```bash
docker compose up -d
```

**What happens:**
1. PostgreSQL 15 starts → runs `db/init.sql` (creates 4 tables + triggers + indexes)
2. Redis 7 starts
3. n8n starts → connects to PostgreSQL for persistence
4. Metabase starts → first-run wizard on http://localhost:3000
5. API starts → loads NLP model from `nlp/models/` (if already trained)

**Wait for all services:**
```bash
docker compose ps
# All should show "healthy" or "running"
```

Expected output:
```
NAME                    STATUS          PORTS
leadgen360-postgres-1   Up (healthy)    0.0.0.0:5432->5432/tcp
leadgen360-redis-1      Up              0.0.0.0:6379->6379/tcp
leadgen360-n8n-1        Up              0.0.0.0:5678->5678/tcp
leadgen360-metabase-1   Up              0.0.0.0:3000->3000/tcp
leadgen360-api-1        Up (healthy)    0.0.0.0:8000->8000/tcp
```

---

### Step 7: Train the NLP Model

```bash
python -m nlp.trainer
```

This:
1. Loads `nlp/data/training_data.py` (300+ examples)
2. Downloads `paraphrase-multilingual-MiniLM-L12-v2` from HuggingFace (~45 MB, first time only)
3. Encodes all training texts to 384-dim vectors
4. Trains 3 LogisticRegression classifiers (sector / tech / priority)
5. Runs 5-fold cross-validation
6. Saves models to `nlp/models/*.joblib`
7. Generates `nlp/reports/evaluation_summary.json` and confusion matrix PNGs

Expected output:
```
[NLP] Loading training data... 364 examples
[NLP] Encoding with SentenceTransformers...
[NLP] Training sector_clf... done (30s)
[NLP] Training tech_clf... done (12s)
[NLP] Training priority_clf... done (8s)
[NLP] Cross-validation: sector F1 = 0.84 ± 0.03
[NLP] Models saved to nlp/models/
```

---

### Step 8: Set Up Metabase Dashboard

1. Open http://localhost:3000
2. Click "Get started" (first-time wizard)
3. Create admin account: use `ferjenimelek42@gmail.com` or any email
4. **Connect your database:**
   - Type: PostgreSQL
   - Host: `postgres` (Docker internal hostname)
   - Port: `5432`
   - Database: `leadgen360`
   - Username: `leadgen`
   - Password: *(value from .env)*
5. Skip "Add your data" sample data
6. Create dashboards or import from `docs/metabase_export.json` if available

---

### Step 9: Import n8n Workflows

1. Open http://localhost:5678 (admin / admin123)
2. Go to **Workflows → Import from file**
3. Import each file from `n8n_workflows/`:
   - `01_linkedin_hiring.json`
   - `02_boamp_rss.json`
   - `03_live_demo.json`
   - `04_collect_trigger.json`
4. For each workflow, click **Edit → Credentials** and update the API key node with your `API_KEY` from `.env`
5. Activate workflows with the toggle

---

### Step 10: Authenticate LinkedIn

LinkedIn requires a one-time login to generate session cookies:

```bash
python -c "
from collectors.linkedin_client import LinkedInClient
client = LinkedInClient(1)  # uses account 1 from .env
client.authenticate()
print('Authenticated! Cookie saved to cookies/session_1.json')
"
```

If you see `CHALLENGE_REQUIRED`, LinkedIn is asking for 2FA:
1. Log in manually at linkedin.com in a browser
2. Complete any security verification
3. Re-run the authentication command

Repeat for accounts 2 and 3 if configured.

---

### Step 11: Run First Collection

```bash
# Dry run first (no DB inserts, just print what would be collected)
python -m collectors.run_all --dry-run

# Real collection
python -m collectors.run_all

# Or specific sources
python -m collectors.run_all --source boamp    # safest: no auth needed
python -m collectors.run_all --source ted      # EU tenders
python -m collectors.run_all --source linkedin # LinkedIn (requires authenticated cookies)
```

---

### Step 12: Verify Everything Works

```bash
docker compose ps
curl http://localhost:8000/health
```

Expected:
```
✅ API healthy at http://localhost:8000/health
✅ PostgreSQL: 12 companies, 47 opportunities, 3 leads
✅ NLP model loaded: sector_clf, tech_clf, priority_clf
✅ n8n: 4 workflows active
✅ Metabase: accessible at http://localhost:3000
```

Test the full pipeline manually:
```bash
# 1. Insert a test prospect
curl -X POST http://localhost:8000/api/ingest \
  -H "X-API-Key: my-secret-api-key-change-this" \
  -H "Content-Type: application/json" \
  -d '{
    "prospects": [{
      "company_name": "BNP Paribas",
      "company_linkedin_url": "https://linkedin.com/company/bnp-paribas",
      "country_iso": "FR",
      "technology": "COBOL",
      "opportunity_type": "outsourcing_signal",
      "sector_hint": "Finance/Banque",
      "title": "Recrute 3 développeurs COBOL"
    }]
  }'

# 2. Check it was classified
curl http://localhost:8000/api/prospects?score=50 \
  -H "X-API-Key: my-secret-api-key-change-this"

# 3. Generate message
curl -X POST http://localhost:8000/api/generate/message \
  -H "X-API-Key: my-secret-api-key-change-this" \
  -H "Content-Type: application/json" \
  -d '{"opportunity_id": "<id-from-step-2>"}'
```

---

### Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| `CHALLENGE_REQUIRED` on LinkedIn | Session expired | Re-authenticate: `python -c "from collectors.linkedin_client import LinkedInClient; LinkedInClient(1).authenticate()"` |
| API returns 503 on `/api/classify` | NLP model not trained | Run `python -m nlp.trainer` |
| Metabase shows no data | Wrong PostgreSQL host | Use `postgres` (not `localhost`) in Metabase settings |
| `docker compose up` fails on port 5432 | Another PostgreSQL running | Stop it: `sudo systemctl stop postgresql` |
| Groq API 429 error | Rate limit (free tier) | Wait 60s or activate Ollama fallback |
| `sentence_transformers` download fails | No internet / firewall | Set `LEADGEN_USE_TFIDF=1` in `.env` for offline fallback |
| `asyncpg.InvalidCatalogNameError` | Database not created | `docker compose down -v && docker compose up -d` (recreates DB) |

---

## 💻 Usage & Commands

### Common Commands

```bash
# ─── Infrastructure ───────────────────────────────────────
docker compose up -d                        # Start all 5 Docker services
docker compose down                         # Stop all services (data preserved)
docker compose up -d --build api            # Rebuild FastAPI Docker image + restart

# ─── Data Collection ──────────────────────────────────────
python -m collectors.run_all                # Run all collectors
python -m collectors.run_all --dry-run      # Simulation — print results without DB inserts
python -m collectors.run_all --source linkedin      # LinkedIn jobs only
python -m collectors.run_all --source linkedin_b2b  # LinkedIn B2B posts only
python -m collectors.run_all --source boamp         # French public tenders only
python -m collectors.run_all --source ted           # EU tenders (BE, LU, CH) only
python -m collectors.run_all --source malt          # Malt.fr freelance only

# ─── NLP ──────────────────────────────────────────────────
python -m nlp.trainer                       # Train + evaluate NLP models (saves .joblib)
python -m nlp.evaluator                     # Run evaluation only (no retrain)

# ─── Database ─────────────────────────────────────────────
docker compose exec postgres psql -U leadgen leadgen360   # Open psql shell

# ─── Monitoring ───────────────────────────────────────────
docker compose ps                           # Service status
curl http://localhost:8000/health           # API health check
docker compose logs -f api                  # Tail FastAPI container logs

# ─── Testing ──────────────────────────────────────────────
pytest tests/ --cov                         # Run pytest tests with coverage
```

### Useful Database Queries

```sql
-- Top opportunities by score
SELECT c.name, o.technology[1], o.priority_score, o.sector_label, o.country
FROM opportunities o JOIN companies c ON o.company_id = c.id
WHERE o.status = 'new'
ORDER BY o.priority_score DESC
LIMIT 20;

-- Distribution by country and sector
SELECT country, sector_label, count(*), round(avg(priority_score)) as avg_score
FROM opportunities
GROUP BY country, sector_label
ORDER BY count DESC;

-- Leads generated this week
SELECT l.id, c.name, l.status, l.generated_linkedin_msg
FROM leads l
JOIN opportunities o ON l.opportunity_id = o.id
JOIN companies c ON o.company_id = c.id
WHERE l.created_at > NOW() - INTERVAL '7 days';

-- NLP confidence distribution
SELECT priority_label, count(*), round(avg(nlp_confidence)::numeric, 2) as avg_conf
FROM opportunities
GROUP BY priority_label;
```

---

## 🔌 API Reference

All routes require `X-API-Key` header (value from `.env` `API_KEY`).

Interactive docs: http://localhost:8000/docs

| Method | Endpoint | Body | Returns |
|--------|----------|------|---------|
| `GET` | `/health` | — | `{status, db, nlp_model, uptime}` |
| `POST` | `/api/ingest` | `{prospects: [...]}` | `{inserted: N, skipped: M}` |
| `POST` | `/api/classify` | `{text, opportunity_id?}` | `{sector_label, tech_label, priority_label, nlp_confidence}` |
| `POST` | `/api/generate/message` | `{opportunity_id, contact_id?}` | `{lead_id, linkedin_message, email_draft}` |
| `GET` | `/api/prospects` | `?score=70&country=FR` | `[{opportunity + company}]` |
| `POST` | `/api/collect/all` | — | `{linkedin: N, boamp: M, ted: K}` |
| `POST` | `/api/collect/linkedin` | — | `{jobs: N, posts: M}` |

---

## 🛡️ Compliance & Ethics

### GDPR / RGPD

The system only collects **professional public data**:
- LinkedIn company pages and job postings (public by design)
- Government procurement notices (legally mandated to be public: BOAMP, TED)
- Freelance project listings (public marketplace)

No personal data of individuals is stored without consent. The `contacts` table is reserved for future use with explicit opt-in. Legal basis for B2B prospecting: Article 6(1)(f) RGPD — **legitimate interest**.

### LinkedIn Terms of Service

`linkedin-api` uses LinkedIn's unofficial internal API, which violates LinkedIn's Terms of Service regarding automated scraping. This project is:
- Built for **educational/research purposes** as part of an academic internship
- **Not deployed at production scale** against LinkedIn's infrastructure

**For production use:** Migrate to LinkedIn Marketing Solutions API (official, paid, ToS-compliant).

### Data Security

- `.env` file is in `.gitignore` — never committed
- `cookies/` directory is in `.gitignore` — LinkedIn sessions never leave the machine
- All API routes require `X-API-Key` authentication
- JWT infrastructure in place (`python-jose`) for future role-based access
- PostgreSQL only accessible within Docker network (not exposed externally by default)

---

## 📈 Live Demo — Soutenance Script (90 seconds)

| Time | Action | Shows |
|------|--------|-------|
| 0–10s | Open http://localhost:3000 → "LeadGen 360+" dashboard | KPIs: prospect count by country, avg score, tech distribution |
| 10–20s | Open http://localhost:5678 → Workflow "03 — Live Demo" → Execute | n8n visual workflow |
| 20–45s | Watch steps execute in real time | POST ingest → classify → generate |
| 45–70s | Display result in n8n output node | Personalized LinkedIn message mentioning the specific signal |
| 70–90s | Refresh Metabase | New prospect appears with NLP labels + score |

**Terminal alternative:** run the three curl commands from Step 12 in sequence (ingest → classify → generate/message).

---

*Built with Python 3.11 + FastAPI + PostgreSQL 15 + sentence-transformers + Groq + n8n + Metabase + Docker — Solvinya Group B2B Lead Generation Platform v1.0*
