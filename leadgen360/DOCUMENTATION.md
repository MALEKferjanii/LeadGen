# LeadGen Francophone 360+ — Documentation Technique Complète

> **Plateforme de génération de leads B2B IT pour Solvinya Group**  
> Cible : entreprises en France · Belgique · Luxembourg · Suisse · Tunisie  
> Stack : Python 3.11 · FastAPI · PostgreSQL · n8n · Metabase · Docker  
> Version : 1.0 — Mai 2026

---

## Table des matières

1. [Résumé exécutif](#1-résumé-exécutif)
2. [Architecture globale](#2-architecture-globale)
3. [Les 5 collecteurs en détail](#3-les-5-collecteurs-en-détail)
4. [Pipeline d'ingestion et scoring](#4-pipeline-dingestion-et-scoring)
5. [Module NLP](#5-module-nlp)
6. [Générateur de messages LLM](#6-générateur-de-messages-llm)
7. [API REST FastAPI](#7-api-rest-fastapi)
8. [Les 4 workflows n8n](#8-les-4-workflows-n8n)
9. [Base de données PostgreSQL](#9-base-de-données-postgresql)
10. [Dashboard Metabase](#10-dashboard-metabase)
11. [Installation sur un nouveau PC](#11-installation-sur-un-nouveau-pc)
12. [Démonstrations pas-à-pas](#12-démonstrations-pas-à-pas)
13. [Référence des commandes](#13-référence-des-commandes)
14. [Résultats actuels](#14-résultats-actuels)
15. [Structure complète des fichiers](#15-structure-complète-des-fichiers)

---

## 1. Résumé exécutif

### Le problème business

Solvinya Group est une ESN (Entreprise de Services Numériques). Son équipe commerciale doit trouver des **entreprises qui ont un besoin actif en services IT** : externalisation, sous-traitance, réponse à appel d'offres. Sans outil automatisé, les commerciaux passent plusieurs heures par semaine à chercher manuellement sur LinkedIn, BOAMP et les journaux officiels pour obtenir quelques leads de qualité incertaine.

### La solution

LeadGen 360+ est un pipeline entièrement automatisé qui :

1. **Scrape** 6 sources de données différentes (LinkedIn, BOAMP, TED EU, Codeur, Twago) toutes les 12 heures
2. **Qualifie** chaque prospect avec un score 0-100 basé sur des règles métier déterministes
3. **Classe** les prospects par secteur et priorité via un modèle NLP
4. **Génère** des messages LinkedIn et emails de prospection personnalisés via LLM (Groq)
5. **Expose** tout via une API REST et des dashboards Metabase

### Les 5 types de signaux détectés

```
┌──────────────────────┬─────────────────────────────────────────────────────┬──────────────┐
│ Type de signal       │ Ce que ça signifie                                  │ Source       │
├──────────────────────┼─────────────────────────────────────────────────────┼──────────────┤
│ b2b_tender           │ Appel d'offres public ou privé pour un projet IT    │ BOAMP, TED,  │
│                      │ Ex: "Marché maintenance logiciel SAP — Mairie Paris" │ LinkedIn B2B │
├──────────────────────┼─────────────────────────────────────────────────────┼──────────────┤
│ b2b_rfp              │ Demande de Proposition formelle (RFP/DDP)           │ LinkedIn B2B │
│                      │ Ex: banque qui publie un appel à candidatures DSI   │              │
├──────────────────────┼─────────────────────────────────────────────────────┼──────────────┤
│ b2b_subcontracting   │ Recherche prestataire / sous-traitance / freelance   │ LinkedIn B2B │
│                      │ Ex: "Recherche prestataire Java pour projet 6 mois"  │ Codeur, Twago│
├──────────────────────┼─────────────────────────────────────────────────────┼──────────────┤
│ b2b_partnership      │ Partenariat, co-traitance, consortium               │ LinkedIn B2B │
│                      │ Ex: "Partenariat stratégique avec cabinet IT"        │              │
├──────────────────────┼─────────────────────────────────────────────────────┼──────────────┤
│ outsourcing_signal   │ Entreprise NON-IT qui recrute un dev → cible pour   │ LinkedIn     │
│                      │ externalisation. Solvinya propose une équipe AVANT  │ Jobs         │
│                      │ que le recrutement aboutisse.                        │              │
└──────────────────────┴─────────────────────────────────────────────────────┴──────────────┘
```

---

## 2. Architecture globale

### Vue macro du système

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                         SOURCES EXTERNES                                      ║
║                                                                                ║
║  ┌─────────────┐  ┌──────────────┐  ┌────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐   ║
║  │ LinkedIn    │  │ LinkedIn     │  │ BOAMP  │  │ TED EU │  │ Codeur   │  │ Twago    │   ║
║  │ Jobs        │  │ Posts (B2B)  │  │ France │  │FR/BE/  │  │ .com     │  │Freelance │   ║
║  │(offres      │  │(publications │  │(marchés│  │LU/CH   │  │(missions │  │(missions │   ║
║  │ emploi IT)  │  │ entreprises) │  │publics)│  │publics)│  │ freelance│  │ FR/BE/CH)│   ║
║  └──────┬──────┘  └──────┬───────┘  └───┬────┘  └───┬────┘  └────┬─────┘  └────┬─────┘   ║
╚═════════╪═══════════════╪══════════════╪═══════════╪════════════╪═════════════╪═══════════╝
          │               │              │           │            │
          ▼               ▼              ▼           ▼            ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                      COUCHE COLLECTEURS (Python)                              ║
║                                                                                ║
║  linkedin_hiring.py  linkedin_b2b.py  boamp.py   ted.py      codeur.py  twago.py    ║
║  (async, session     (regex scoring   (httpx GET  (httpx POST (httpx GET  (httpx GET  ║
║   pooling 2 comptes)  sur posts)       open data)  expert QL)  HTML+JSON)  FR/BE/CH) ║
║         │                  │              │           │            │           │        ║
║         └──────────────────┴──────────────┴───────────┴────────────┴───────────┘       ║
║                                     │                                          ║
║                              run_all.py                                        ║
║                        (orchestrateur séquentiel                               ║
║                         argparse --source filter)                              ║
╚═════════════════════════════════════╪════════════════════════════════════════╝
                                      │
                                      ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                      PIPELINE D'INGESTION (Python)                            ║
║                                                                                ║
║   pipeline/ingest.py                                                           ║
║   ┌─────────────────────────────────────────────────────────────────────┐     ║
║   │  1. Normalise les champs (company_name, tech, country_iso, …)       │     ║
║   │  2. UPSERT entreprise dans companies (LinkedIn URL = clé unique)    │     ║
║   │  3. DÉDUPLIQUE : même entreprise + même techno dans les 30 derniers │     ║
║   │     jours → skip                                                     │     ║
║   │  4. Calcule score règle-métier 0-100 (scorer_rules.py)              │     ║
║   │  5. Génère titre contextuel selon opportunity_type                  │     ║
║   │  6. INSERT dans opportunities                                        │     ║
║   └─────────────────────────────────────────────────────────────────────┘     ║
╚═════════════════════════════════════╪════════════════════════════════════════╝
                                      │
                                      ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                    BASE DE DONNÉES PostgreSQL 15                               ║
║                                                                                ║
║   ┌────────────┐  ┌──────────────────┐  ┌────────────┐  ┌────────────────┐  ║
║   │ companies  │  │  opportunities   │  │  contacts  │  │     leads      │  ║
║   │            │◄─┤                  │  │            │  │                │  ║
║   │ id (UUID)  │  │ id, company_id   │  │ id, full_  │  │ id, opp_id,    │  ║
║   │ name       │  │ title, type,     │  │ name, job_ │  │ contact_id,    │  ║
║   │ linkedin_  │  │ technologies[],  │  │ title,     │  │ linkedin_msg,  │  ║
║   │ url        │  │ priority_score,  │  │ email,     │  │ email_msg,     │  ║
║   │ country    │  │ source_platform, │  │ linkedin_  │  │ status         │  ║
║   │ sector     │  │ country, status  │  │ url        │  │                │  ║
║   └────────────┘  └──────────────────┘  └────────────┘  └────────────────┘  ║
╚═════════════════════════════════════╪════════════════════════════════════════╝
                                      │
               ┌──────────────────────┼─────────────────────┐
               ▼                      ▼                      ▼
╔═════════════════════╗  ╔══════════════════════╗  ╔════════════════════════╗
║   FastAPI :8000      ║  ║    Metabase :3000    ║  ║      n8n :5678         ║
║                      ║  ║                      ║  ║                        ║
║  /health             ║  ║  Dashboards visuels  ║  ║  4 workflows :         ║
║  /api/ingest         ║  ║  KPIs, graphes,      ║  ║  01 LinkedIn Hiring    ║
║  /api/classify  ─────╫──╫──> requêtes SQL      ║  ║  02 BOAMP RSS          ║
║  /api/generate/ ─────╫──╫──> export CSV        ║  ║  03 Live Demo          ║
║  /api/prospects      ║  ║                      ║  ║  04 Collect Trigger    ║
║  /api/collect/all    ║  ╚══════════════════════╝  ╚════════════════════════╝
╚═════════════════════╝
```

### Vue du cycle de vie d'un prospect

```
[Source externe]
      │
      │  Exemple : TED EU publie "Marché public — Système SAP — Luxembourg"
      │
      ▼
[Collecteur ted.py]
      │  POST https://api.ted.europa.eu/v3/notices/search
      │  query: notice-title="SAP" AND buyer-country=LUX
      │  → extrait buyer-name, notice-title, publication-date, cpv-codes
      │
      ▼
[pipeline/ingest.py : ingest_raw_dict()]
      │
      ├─ UPSERT companies WHERE linkedin_url = "https://ted.europa.eu/LUX-xxx"
      │   → company_id
      │
      ├─ SELECT id FROM opportunities
      │   WHERE company_id = ? AND technologies @> ARRAY['SAP']
      │   AND opportunity_type = 'b2b_tender'
      │   AND created_at > NOW() - INTERVAL '30 days'
      │   → si trouvé : SKIP (doublon)
      │
      ├─ compute_rule_score(country='LU', tech='SAP', sector='Industrie/RH', boost=12+6)
      │   score = (100×0.30) + (85×0.25) + (70×0.25) + (72×0.20)
      │         = 30 + 21.25 + 17.5 + 14.4 = 83
      │
      └─ INSERT INTO opportunities (title, opportunity_type, priority_score=83, …)
            title = "[Appel d'offres] SAP — Gouvernement LU"
            status = 'new'
            │
            ▼
      [PostgreSQL — stocké]
            │
            │  Plus tard, sur demande du commercial :
            ▼
      [POST /api/classify]
            │  TF-IDF + LinearSVC → sector_label="Industrie/RH", priority="HIGH", conf=0.89
            ▼
      [POST /api/generate/message]
            │  Groq llama-3.1-8b → message LinkedIn personnalisé en 5 lignes
            ▼
      [Message prêt à envoyer sur LinkedIn]
```

---

## 3. Les 5 collecteurs en détail

### 3.1 LinkedIn Jobs — Signal Externalisation

**Fichier** : `collectors/linkedin_hiring.py`  
**Signal produit** : `outsourcing_signal`  
**Logique B2B** : une banque qui recrute un développeur COBOL a un projet COBOL actif avec budget. Solvinya peut contacter le DSI pour proposer une équipe externalisée immédiatement disponible — souvent plus rapide et moins cher qu'un recrutement CDI pour un profil rare.

#### Flux technique complet

```
┌──────────────────────────────────────────────────────────────────────┐
│                   linkedin_hiring.py :: collect()                     │
│                                                                        │
│  OUTER LOOP: for (tech, countries, boost) in JOB_SEARCHES:           │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Ex: tech="COBOL", countries=["France","Belgique",…]          │    │
│  │                                                                │    │
│  │  INNER LOOP: for country in countries:                        │    │
│  │  ┌────────────────────────────────────────────────────────┐  │    │
│  │  │  client.search_jobs(keywords="COBOL", location=country │  │    │
│  │  │                     limit=30)                          │  │    │
│  │  │       │                                                │  │    │
│  │  │       │ Retourne: [{entityUrn: "urn:li:job:123", …}]  │  │    │
│  │  │       ▼                                                │  │    │
│  │  │  for stub in job_stubs:                                │  │    │
│  │  │    job_id = extract_job_id(stub["entityUrn"])          │  │    │
│  │  │    full_job = client.get_job(job_id)       ← détail   │  │    │
│  │  │    info = _extract_company_info(full_job)              │  │    │
│  │  │    # navigue: companyDetails                           │  │    │
│  │  │    #          → companyResolutionResult                │  │    │
│  │  │    #          → universalName, name                    │  │    │
│  │  │    prospect = HiringProspect(                          │  │    │
│  │  │      company_name, linkedin_url, country, tech, …)    │  │    │
│  │  │    ingest_opportunity(prospect,                        │  │    │
│  │  │      opportunity_type="outsourcing_signal")            │  │    │
│  │  │    sleep(gauss(4.0, 1.5))   ← anti-détection          │  │    │
│  │  └────────────────────────────────────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

#### Technologies et pays surveillés

```
TECHNOLOGIES CIBLÉES               PAYS CIBLES (limit par pays)
──────────────────────────────     ────────────────────────────
COBOL           boost +25          France      : 30 leads/tech
Mainframe       boost +25          Belgique    : 20 leads/tech
Python          boost +15          Luxembourg  : 15 leads/tech
Machine Learning boost +15         Suisse      : 15 leads/tech
SAP             boost +12          Tunisie     : 20 leads/tech
Data Engineer   boost +12
Java            boost +10
DevOps          boost +10
Salesforce      boost  +8
React           boost  +5
```

#### Anti-détection

- Délai gaussien entre requêtes : `random.gauss(4.0, 1.5)` secondes
- Rotation automatique de 2 comptes LinkedIn (`session_manager.py`)
- Cookies persistés sur disque pour éviter les re-authentifications

---

### 3.2 LinkedIn B2B — Signaux Directs

**Fichier** : `collectors/linkedin_b2b.py`  
**Signaux produits** : `b2b_rfp`, `b2b_tender`, `b2b_subcontracting`, `b2b_partnership`  
**Logique** : chercher les entreprises ACHETEUSES (banques, assurances, industrie, santé) et scanner leurs publications LinkedIn récentes pour y détecter des besoins B2B explicites.

#### Pourquoi cette approche (et pas search_content) ?

L'API LinkedIn non-officielle ne retourne aucun résultat avec le filtre `CONTENT` sur les posts. La stratégie est donc indirecte :

```
search_content("appel d'offres Java")  →  0 résultats  ← ne fonctionne PAS
                                                          (limitation API non-officielle)

search_companies("banque crédit France") → [Crédit Agricole, BNP, …]
                                              ↓
get_company_updates_by_id(urn_id)        → derniers posts de la page
                                              ↓
regex _score_post(text)                  → signal B2B détecté ?  ← FONCTIONNE
```

#### Flux technique complet

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    linkedin_b2b.py :: collect()                                │
│                                                                                │
│  for (search_query, sector, boost) in BUYER_SEARCH_QUERIES:                  │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  Ex: ("banque crédit financement France", "Finance/Banque", 20)       │    │
│  │                                                                        │    │
│  │  companies = client.search_companies(keywords=query, limit=8)         │    │
│  │  # Retourne: [{name: "Crédit Agricole", urn_id: 2477843, …}]          │    │
│  │                                                                        │    │
│  │  for company in companies:                                             │    │
│  │  ┌────────────────────────────────────────────────────────────────┐   │    │
│  │  │  signals = _scan_company(urn_id, name, sector, boost)          │   │    │
│  │  │  ┌──────────────────────────────────────────────────────────┐  │   │    │
│  │  │  │  updates = client.get_company_updates_by_id(urn_id, 15)  │  │   │    │
│  │  │  │  for update in updates:                                   │  │   │    │
│  │  │  │    text = _extract_post_text(update)                      │  │   │    │
│  │  │  │    if len(text) < 40: continue                            │  │   │    │
│  │  │  │    if _ESN_INDICATORS.search(text[:200]): continue ──────▶│  │   │    │
│  │  │  │    # FILTRE : exclure les ESN/prestataires                │  │   │    │
│  │  │  │    # qui publient leurs propres services                  │  │   │    │
│  │  │  │    opp_type, tech, boost = _score_post(text)             │  │   │    │
│  │  │  │    if opp_type: signals.append({…})                       │  │   │    │
│  │  │  └──────────────────────────────────────────────────────────┘  │   │    │
│  │  │  for sig in signals:                                            │   │    │
│  │  │    if sig["post_id"] in seen_keys: continue  ← dédup mémoire   │   │    │
│  │  │    ingest_raw_dict(sig, source_platform="linkedin_b2b")        │   │    │
│  │  └────────────────────────────────────────────────────────────────┘   │    │
│  │  sleep(gauss(3.0, 0.8))                                               │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Patterns de détection (regex avec score)

```
PATTERN REGEX                                    TYPE            BOOST
──────────────────────────────────────────────── ─────────────── ─────
rfp|request for proposal|demande de proposition  b2b_rfp         +22
appel d.offres|consultation|marché public        b2b_tender      +18
recherche prestataire|sous-traitan|outsourc       b2b_subcontracting +16
partenariat stratégique|co-traitan|consortium    b2b_partnership +14
sélectionné|retenu|choisi + prestataire          b2b_tender      +12
```

#### Filtre anti-faux-positifs (ESN indicators)

```python
_ESN_INDICATORS = re.compile(
    r'\b(ESN|SSII|société de services informatiques|cabinet de conseil IT'
    r'|nous accompagnons|nos experts|notre expertise|nos consultants|nos solutions)\b'
)
# Si un post d'entreprise contient ces mots → c'est un ESN qui parle de lui-même → SKIP
```

#### Requêtes de recherche d'entreprises acheteuses

```
REQUÊTE                                    SECTEUR               BOOST
─────────────────────────────────────────  ─────────────────── ──────
"banque crédit financement France"          Finance/Banque          20
"assurance mutuelle France prévoyance"      Finance/Assurance       18
"caisse épargne crédit populaire"           Finance/Banque          20
"mairie métropole communauté agglomération" Secteur public          14
"région département conseil général France" Secteur public          13
"hôpital CHU santé publique France"         Santé                   14
"groupe industriel France fabrication usine" Industrie/RH           14
"énergie électricité réseau infrastructure"  Energie                15
"transport logistique France supply chain"   Transport              13
"distribution retail commerce grande surface" Retail                12
"banque tunisie financement"                Finance/Banque          18
"entreprise industrielle tunisie production" Industrie/RH           14
```

---

### 3.3 BOAMP — Marchés Publics France

**Fichier** : `collectors/boamp.py`  
**Signal produit** : `b2b_tender`  
**Source** : API officielle gratuite — Bulletin Officiel des Annonces de Marchés Publics  
**URL** : `https://boamp-datadila.opendatasoft.com/api/explore/v2.1/catalog/datasets/boamp/records`

#### Flux technique complet

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        boamp.py :: collect()                                   │
│                                                                                │
│  for tech in TECH_KEYWORDS:  (15 mots-clés)                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  GET /records                                                          │    │
│  │    ?where=objet like "{tech}"                                          │    │
│  │    &limit=20                                                            │    │
│  │    &order_by=dateparution desc                                          │    │
│  │    &select=objet,nomacheteur,url_avis,dateparution,nature_libelle       │    │
│  │         │                                                               │    │
│  │         ▼                                                               │    │
│  │  for rec in results["records"]:                                        │    │
│  │    ingest_raw_dict({                                                   │    │
│  │      "company_name": rec["nomacheteur"],      ← ex: "Mairie de Lyon"  │    │
│  │      "company_linkedin_url":                                           │    │
│  │          f"https://boamp.fr/{rec['url_avis']}",                        │    │
│  │      "job_title": rec["objet"],               ← titre du marché       │    │
│  │      "job_url": rec["url_avis"],                                       │    │
│  │      "location": "France",                                             │    │
│  │      "country_iso": "FR",                                              │    │
│  │      "technology": tech,                                               │    │
│  │      "sector_hint": _detect_sector(rec["nomacheteur"]),               │    │
│  │      "priority_boost": boost_for_tech[tech],                          │    │
│  │      "opportunity_type": "b2b_tender",                                │    │
│  │    }, source_platform="boamp")                                        │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
│  sleep(0.3)  ← respecter les limites de l'API publique                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Mots-clés IT surveillés

```
SAP · COBOL · Java · Python · DevOps · cloud · cybersécurité
intelligence artificielle · machine learning · data · ERP
infrastructure · développement · logiciel · informatique
```

#### Résultat typique

```
~215-236 prospects par collecte
Acheteurs : ministères, collectivités, hôpitaux, établissements publics
Score moyen : 66/100
Tous tagués : b2b_tender / source_platform = boamp
```

---

### 3.4 TED EU — Marchés Publics Européens

**Fichier** : `collectors/ted.py`  
**Signal produit** : `b2b_tender`  
**Source** : API officielle gratuite — Tenders Electronic Daily (Journal Officiel UE)  
**URL** : `https://api.ted.europa.eu/v3/notices/search`  
**Méthode** : POST uniquement (GET retourne 405)

#### Syntaxe de requête expert

```
POST /v3/notices/search
{
  "query": "notice-title=\"SAP\" AND buyer-country=FRA",
  "fields": ["notice-title", "buyer-name", "publication-date",
             "notice-url", "cpv-codes", "lot-value"],
  "limit": 15
}
```

Points importants :
- Chaque requête = **un pays + un mot-clé** (pas de multi-pays dans une requête)
- Le nom de l'acheteur `buyer-name` est un dict multilingue → préférer `.get("fra")` puis `.get("eng")`
- Les codes pays : `FRA`, `BEL`, `LUX`, `CHE` (et non FR, BE, LU, CH)

#### Flux technique complet

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                         ted.py :: collect()                                    │
│                                                                                │
│  for country_code in ["FRA", "BEL", "LUX", "CHE"]:                          │
│  ┌──────────────────────────────────────────────────────────────────────┐    │
│  │  for keyword in IT_TITLE_KEYWORDS:  (14 mots-clés)                   │    │
│  │  ┌────────────────────────────────────────────────────────────────┐  │    │
│  │  │  notices = await _search(country_code, keyword, limit=15)      │  │    │
│  │  │  ┌──────────────────────────────────────────────────────────┐  │  │    │
│  │  │  │  POST https://api.ted.europa.eu/v3/notices/search         │  │  │    │
│  │  │  │  body: {                                                   │  │  │    │
│  │  │  │    "query": f'notice-title="{keyword}"                    │  │  │    │
│  │  │  │             AND buyer-country={country_code}',            │  │  │    │
│  │  │  │    "fields": TED_FIELDS,                                  │  │  │    │
│  │  │  │    "limit": 15                                            │  │  │    │
│  │  │  │  }                                                        │  │  │    │
│  │  │  │  → retourne: {"notices": [{…}, …]}                       │  │  │    │
│  │  │  └──────────────────────────────────────────────────────────┘  │  │    │
│  │  │                                                                  │  │    │
│  │  │  for notice in notices:                                          │  │    │
│  │  │    buyer = notice.get("buyer-name", {})                          │  │    │
│  │  │    name = buyer.get("fra") or buyer.get("eng") or "Acheteur EU"  │  │    │
│  │  │    title = notice.get("notice-title", {})                        │  │    │
│  │  │    title_text = title.get("fra") or title.get("eng") or keyword  │  │    │
│  │  │    ingest_raw_dict({                                              │  │    │
│  │  │      "company_name": name,                                        │  │    │
│  │  │      "country_iso": country_code[:2],  ← "FR","BE","LU","CH"     │  │    │
│  │  │      "technology": detect_tech(title_text, keyword),             │  │    │
│  │  │      "opportunity_type": "b2b_tender",                           │  │    │
│  │  │      "priority_boost": boost_for_country[country_code],          │  │    │
│  │  │      …                                                            │  │    │
│  │  │    }, source_platform="ted")                                      │  │    │
│  │  └────────────────────────────────────────────────────────────────┘  │    │
│  │  sleep(1.0)                                                           │    │
│  └──────────────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Mots-clés IT pour TED

```
logiciel · informatique · système · développement · SAP · ERP
cloud · cybersécurité · infrastructure · réseau · données · IA
Java · Python
```

#### Résultats par pays (collecte de mai 2026)

```
Pays   Code   Prospects   Score moyen   Boost pays
────── ────── ─────────── ─────────────────────────
France FRA    145          65            base
Belgique BEL  105          63            +3
Suisse  CHE    98          65            +5
Luxembourg LUX  74         66            +10 (priorité max)
──────────────────────────────────────────────────
TOTAL          422
```

---

### 3.5 Codeur.com — Missions Freelance IT France

**Fichier** : `collectors/codeur.py`  
**Signal produit** : `b2b_subcontracting`  
**Source** : Plateforme publique, pas d'authentification requise  
**URL** : `https://www.codeur.com/projets`

#### Logique B2B

Une entreprise qui publie une mission freelance sur Codeur.com a un **besoin IT confirmé avec budget disponible**. C'est un signal de sous-traitance direct : la société cherche un prestataire externe, Solvinya peut se positionner.

#### Catégories surveillées

```
Slug                          Technologie        Secteur           Boost
────────────────────────────  ─────────────────  ────────────────  ─────
dev-logiciel                  Python             Tech              12
dev-web                       React              Tech/e-commerce    8
reseau-systemes-securite      DevOps             Tech              10
dev-mobile                    React              Tech               7
erp-crm                       SAP                Industrie/RH      12
intelligence-artificielle     Machine Learning   Tech/IA           15
big-data                      Data Engineer      Tech/IA           12
java                          Java               Finance/Banque    10
```

#### Flux technique

```
GET https://www.codeur.com/projets?category={slug}&page=1
    │
    ├─ Tentative 1 : extraction JSON embarqué (window.__INITIAL_STATE__)
    │   → projets[].title, .user.company, .description, .budget, .slug
    │
    └─ Fallback : regex HTML sur <article class="project*">
        → h2/h3 → titre
        → patron budget : \d[\d\s]*€
        → href="/projets/{slug}"
```

Délai entre requêtes : 2 secondes.

---

### 3.6 TwagoFreelance.com — Missions Freelance IT Europe Francophone

**Fichier** : `collectors/twago.py`  
**Signal produit** : `b2b_subcontracting`  
**Source** : Plateforme publique, pas d'authentification requise  
**URL** : `https://www.twagofreelance.com/fr/projets-freelance`

#### Logique B2B

Twago couvre la France, la Belgique et la Suisse — des marchés prioritaires pour Solvinya. Chaque mission publiée = besoin IT confirmé + budget disponible + délai court.

#### Catégories et pays surveillés

```
Slug                          Technologie        Secteur     Boost  Pays
────────────────────────────  ─────────────────  ──────────  ─────  ────
informatique                  Python             Tech          12    FR
developpement-web             React              Tech/e-comm    8    FR
java                          Java               Finance/Banq  10    FR
devops-cloud                  DevOps             Tech          10    FR
data-science                  Machine Learning   Tech/IA       15    FR
erp-sap                       SAP                Industrie/RH  12    FR
securite-informatique         DevOps             Tech          10    BE
intelligence-artificielle     Machine Learning   Tech/IA       15    BE
developpement-logiciel        Python             Tech          12    CH
```

#### Flux technique

```
GET https://www.twagofreelance.com/fr/projets-freelance/{slug}
    │
    ├─ Tentative 1 : extraction JSON embarqué
    │   Patterns testés :
    │   - window.__INITIAL_DATA__ = {...}
    │   - var pageData = {...}
    │   - <script type="application/json">
    │   → projets[].title, .company.name, .description, .budget, .url
    │
    ├─ 404 → Fallback URL : GET /fr/projets-freelance?q={technology}
    │
    └─ Fallback HTML : regex sur <article|div class="*project|mission|offer*">
        → h1-h4 → titre
        → patron budget : \d[\d\s]*€
        → href="/.*projet|project|mission.*"
```

Délai entre requêtes : 2 secondes.

---

### Tableau récapitulatif des collecteurs

```
┌──────────────────┬───────────────────┬───────────────┬────────────┬────────────┐
│ Collecteur       │ Signal produit    │ Pays couverts │ Fréquence  │ Statut     │
├──────────────────┼───────────────────┼───────────────┼────────────┼────────────┤
│ linkedin_hiring  │ outsourcing_signal│ FR BE LU CH TN│ 12h (n8n)  │ ✅ Actif   │
├──────────────────┼───────────────────┼───────────────┼────────────┼────────────┤
│ linkedin_b2b     │ b2b_tender        │ FR TN         │ 12h (n8n)  │ ✅ Actif   │
│                  │ b2b_rfp           │ (principalement)│          │ (limité)   │
│                  │ b2b_partnership   │               │            │            │
│                  │ b2b_subcontracting│               │            │            │
├──────────────────┼───────────────────┼───────────────┼────────────┼────────────┤
│ boamp            │ b2b_tender        │ FR (public)   │ 12h (n8n)  │ ✅ Actif   │
├──────────────────┼───────────────────┼───────────────┼────────────┼────────────┤
│ ted              │ b2b_tender        │ FR BE LU CH   │ 12h (n8n)  │ ✅ Actif   │
│                  │                   │ (public EU)   │            │            │
├──────────────────┼───────────────────┼───────────────┼────────────┼────────────┤
│ codeur           │ b2b_subcontracting│ FR            │ 12h (n8n)  │ ✅ Actif   │
├──────────────────┼───────────────────┼───────────────┼────────────┼────────────┤
│ twago            │ b2b_subcontracting│ FR BE CH      │ 12h (n8n)  │ ✅ Actif   │
├──────────────────┼───────────────────┼───────────────┼────────────┼────────────┤
│ malt             │ b2b_subcontracting│ FR            │ —          │ ❌ Retiré  │
│                  │                   │               │            │ (Cloudflare│
│                  │                   │               │            │  403)      │
└──────────────────┴───────────────────┴───────────────┴────────────┴────────────┘
```

---

## 4. Pipeline d'ingestion et scoring

### 4.1 Fichier `pipeline/ingest.py`

Ce fichier est le cœur du système. Tous les collecteurs appellent `ingest_raw_dict()` ou directement `ingest_opportunity()`.

#### Diagramme de flux complet

```
ingest_raw_dict(data: dict, source_platform: str)
  │
  ├─ Normalise les champs :
  │   company_name, company_linkedin_url, company_universal_name
  │   job_title, job_url, location, country_iso
  │   technology, sector_hint, priority_boost, opportunity_type
  │
  ▼
ingest_opportunity(prospect: HiringProspect,
                   source_platform: str,
                   opportunity_type: str)
  │
  ├─ ÉTAPE 1 : UPSERT entreprise
  │   INSERT INTO companies (name, linkedin_url, country, sector, source)
  │   ON CONFLICT (linkedin_url) DO UPDATE SET name = EXCLUDED.name
  │   → retourne company_id (UUID)
  │
  ├─ ÉTAPE 2 : DÉDUPLICATION (fenêtre 30 jours)
  │   SELECT id FROM opportunities
  │   WHERE company_id = $1
  │   AND technologies @> ARRAY[$2]     ← même technologie
  │   AND opportunity_type = $3         ← même type de signal
  │   AND created_at > NOW() - INTERVAL '30 days'
  │   → si trouvé → RETURN False (pas d'ingestion)
  │
  ├─ ÉTAPE 3 : SCORING (règle-métier déterministe)
  │   rule_score = compute_rule_score(
  │     country=prospect.country_iso,
  │     technology=prospect.technology,
  │     sector=prospect.sector_hint,
  │     priority_boost=prospect.priority_boost
  │   )
  │
  ├─ ÉTAPE 4 : GÉNÉRATION DU TITRE contextuel
  │   type_labels = {
  │     "outsourcing_signal":   "[Signal externalisation]",
  │     "b2b_rfp":              "[RFP/DDP]",
  │     "b2b_tender":           "[Appel d'offres]",
  │     "b2b_subcontracting":   "[Sous-traitance]",
  │     "b2b_partnership":      "[Partenariat]",
  │   }
  │   title = f"{label} {tech} — {company_name}"
  │   description = f"{label} {tech} à {location}. Détail: {job_title[:200]}"
  │
  └─ ÉTAPE 5 : INSERT opportunité
      INSERT INTO opportunities (
        company_id, title, description, opportunity_type,
        technologies, source_url, source_platform,
        country, priority_score, sector_label, status
      ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'new')
      RETURNING id
      → retourne True (ingestion réussie)
```

---

### 4.2 Formule de scoring (`pipeline/scorer_rules.py`)

#### La formule

```
score = (pays × 0.30) + (technologie × 0.25) + (secteur × 0.25) + (boost × 0.20)
```

Chaque dimension est un score 0-100. Le résultat final est plafonné à 100.

#### Tables de scores par dimension

```
DIMENSION PAYS (poids 30%)        DIMENSION TECHNOLOGIE (poids 25%)
──────────────────────────────    ────────────────────────────────────
Luxembourg      = 100             COBOL           = 100
Suisse          =  95             Mainframe        = 100
France          =  90             SAP              =  85
Belgique        =  85             Java             =  80
Tunisie         =  65             Machine Learning =  78
                                  Data Engineer    =  75
                                  Python           =  70
                                  DevOps           =  70
                                  Salesforce       =  65
                                  Cloud            =  60
                                  React            =  55
                                  Informatique     =  45
                                  (autre)          =  40

DIMENSION SECTEUR (poids 25%)     DIMENSION BOOST (poids 20%)
──────────────────────────────    ────────────────────────────────────
Finance/Banque  = 100             priority_boost vient du collecteur
Finance/Assur.  =  95             (0 à 25 selon la source et le type)
Finance         =  90             Normalisé : boost/25 × 100
IA              =  75             Ex: boost=25 → score_boost=100
Tech/IA         =  72                  boost=12 → score_boost=48
Industrie/RH    =  70
Tech            =  65
CRM/Retail      =  60
Retail          =  50
Santé           =  55
Secteur public  =  50
```

#### Exemples de calculs

```
EXEMPLE 1 : COBOL, Finance/Banque, Luxembourg, boost=25
────────────────────────────────────────────────────────
score = (100 × 0.30) + (100 × 0.25) + (100 × 0.25) + (100 × 0.20)
      =   30          +   25         +   25          +   20
      = 100  ✓ (meilleur score possible)

EXEMPLE 2 : SAP, Industrie/RH, Belgique, boost=12 (TED)
────────────────────────────────────────────────────────
score_boost = (12/25) × 100 = 48
score = (85 × 0.30) + (85 × 0.25) + (70 × 0.25) + (48 × 0.20)
      =  25.5        +  21.25      +  17.5        +   9.6
      = 73.85 → 74

EXEMPLE 3 : React, Tech, France, boost=5 (LinkedIn)
────────────────────────────────────────────────────────
score_boost = (5/25) × 100 = 20
score = (90 × 0.30) + (55 × 0.25) + (65 × 0.25) + (20 × 0.20)
      =  27          +  13.75      +  16.25       +   4
      = 61

EXEMPLE 4 : Python, IA, Suisse, boost=15
────────────────────────────────────────────────────────
score_boost = (15/25) × 100 = 60
score = (95 × 0.30) + (70 × 0.25) + (75 × 0.25) + (60 × 0.20)
      =  28.5        +  17.5       +  18.75       +  12
      = 76.75 → 77
```

---

## 5. Module NLP

### 5.1 Pourquoi un module NLP ?

Le scoring règle-métier est déterministe mais limité : il score sur les champs structurés (pays, tech, secteur). Le NLP permet de classifier le **texte libre** des opportunités (titre, description) pour affiner le secteur et la priorité, notamment pour les données TED et BOAMP qui ont des textes riches.

### 5.2 Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                      OpportunityClassifier                                     │
│                       (nlp/classifier.py)                                     │
│                                                                                │
│  ┌────────────────────────────────┐  ┌────────────────────────────────────┐  │
│  │    Pipeline Secteur             │  │    Pipeline Priorité               │  │
│  │                                 │  │                                    │  │
│  │  input: texte brut              │  │  input: texte brut                 │  │
│  │      ↓                          │  │      ↓                             │  │
│  │  TfidfVectorizer (word 1-3g)    │  │  TfidfVectorizer (word 1-3g)      │  │
│  │   + TfidfVectorizer (char 3-5g) │  │   + TfidfVectorizer (char 3-5g)   │  │
│  │   → FeatureUnion (concat)       │  │   → FeatureUnion (concat)         │  │
│  │      ↓                          │  │      ↓                             │  │
│  │  LinearSVC                      │  │  LinearSVC                         │  │
│  │   + CalibratedClassifierCV      │  │   + CalibratedClassifierCV         │  │
│  │   (pour avoir des probabilités) │  │   (pour avoir des probabilités)    │  │
│  │      ↓                          │  │      ↓                             │  │
│  │  Sortie :                       │  │  Sortie :                          │  │
│  │    sector_label  (str)          │  │    priority_label  (HIGH/MED/LOW)  │  │
│  │    sector_confidence (0.0-1.0)  │  │    priority_confidence (0.0-1.0)   │  │
│  └────────────────────────────────┘  └────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 5.3 Pourquoi TF-IDF et non sentence-transformers ?

```
COMPARAISON sur 604 exemples d'entraînement
───────────────────────────────────────────────────────────────
Modèle                          Accuracy CV-5   Raison
─────────────────────────────── ────────────── ──────────────────────────────────
TF-IDF (word 1-3g + char 3-5g)    75.0%         Vocabulaire technique restreint
Sentence-transformers              69.4%         Meilleur sur corpus larges/sémantiques
Logistic Regression seule          71%           Moins robuste sur les sous-classes

→ TF-IDF gagne sur des mots-clés IT très distincts (COBOL, SAP, DevOps)
→ Les n-grammes de caractères capturent les variantes orthographiques
   (cybersécurité, cyber-sécurité, cybersecurity)
```

### 5.4 Données d'entraînement

```
604 exemples labelisés manuellement dans nlp/data/training_data.py
Répartition par secteur :
  Finance/Banque    : ~120 ex.
  Industrie/RH      : ~100 ex.
  Tech/IA           : ~110 ex.
  Secteur public    : ~90 ex.
  Santé             : ~70 ex.
  Transport/Retail  : ~60 ex.
  Autres            : ~54 ex.
```

### 5.5 Performances

```
Métrique                           Valeur
──────────────────────────────────────────────────────────
Cross-validation 5-fold (secteur)   75.0% ± 4%     ← seuil minimum requis
Accuracy test set (secteur)         70.2%
F1-macro (secteur)                  68%
Accuracy test set (priorité)        85%
```

### 5.6 Entraîner les modèles

```bash
# Lancer l'entraînement (doit atteindre >= 75% CV pour valider)
docker compose exec api python -m nlp.trainer

# Résultat attendu :
# Cross-val 75.0% >= 75%. Modeles prets pour la production.
# Modèles sauvegardés : nlp/models/sector_model.joblib
#                       nlp/models/priority_model.joblib
# Rapport : nlp/reports/evaluation_summary.json
```

---

## 6. Générateur de messages LLM

### 6.1 Architecture

```
POST /api/generate/message  {"opportunity_id": "uuid"}
                │
                ▼
        automation/message_generator.py
                │
                ├─ Lit l'opportunité depuis DB (company, tech, type, score, sector)
                │
                ├─ Construit un prompt adapté au type de signal :
                │
                │  outsourcing_signal  →  "L'entreprise recrute un dev {tech}. Propose l'externalisation."
                │  b2b_tender          →  "L'entreprise a publié un AO IT. Propose une réponse."
                │  b2b_partnership     →  "L'entreprise cherche un partenaire. Présente Solvinya."
                │  b2b_rfp             →  "L'entreprise a publié un RFP. Propose une solution complète."
                │
                ▼
        automation/llm_client.py
                │
                ├─ Tentative 1 : Groq API (llama-3.1-8b-instant)
                │   POST https://api.groq.com/openai/v1/chat/completions
                │   Latence : 1-3 secondes
                │   Gratuit jusqu'à 30 req/min
                │
                └─ Fallback : Ollama local (si Groq indisponible)
                    POST http://localhost:11434/api/generate
                    Modèle : llama3:8b (à télécharger)
                    Latence : 5-15s (selon GPU)
```

### 6.2 Exemple de message généré

```
ENTRÉE : BNP Paribas, COBOL, France, outsourcing_signal, score=95

SORTIE :
────────────────────────────────────────────────────────
Bonjour [Prénom],

J'ai remarqué que BNP Paribas recrute activement des
profils COBOL en ce moment.

Chez Solvinya Group, nous disposons d'une équipe
COBOL/Mainframe disponible immédiatement — nous
intervenons souvent quand le recrutement prend trop
de temps ou que la mission est trop courte pour
justifier un CDI.

Vous travaillez sur une migration ou une maintenance
de système legacy ?
────────────────────────────────────────────────────────
```

---

## 7. API REST FastAPI

### 7.1 Vue d'ensemble

```
http://localhost:8000
        │
        ├── GET  /                     → Redirect vers /docs
        ├── GET  /health               → Santé API + DB
        ├── GET  /docs                 → Swagger UI interactif
        │
        ├── POST /api/ingest           → Ingestion manuelle de prospects
        ├── POST /api/classify         → Classification NLP d'un texte
        ├── GET  /api/prospects        → Liste prospects (pagination, filtres)
        ├── POST /api/generate/message → Génération message LinkedIn
        ├── POST /api/generate/email   → Génération email
        │
        ├── POST /api/collect/linkedin → Déclenche collecte LinkedIn (background)
        └── POST /api/collect/all      → Déclenche collecte complète (background)

Auth : header X-API-Key: <API_SECRET_KEY depuis .env>
```

### 7.2 Chaque endpoint en détail

#### GET /health

```bash
curl http://localhost:8000/health

# Réponse :
{
  "status": "ok",
  "database": "ok",
  "service": "leadgen360-api",
  "version": "1.0.0"
}
```

#### POST /api/ingest

```bash
curl -X POST http://localhost:8000/api/ingest \
  -H "X-API-Key: leadgen360_demo_secret_2024" \
  -H "Content-Type: application/json" \
  -d '{
    "prospects": [{
      "company_name": "BNP Paribas",
      "company_linkedin_url": "https://linkedin.com/company/bnpparibas",
      "company_universal_name": "bnpparibas",
      "job_title": "Développeur COBOL Senior",
      "job_url": "https://linkedin.com/jobs/view/123456",
      "location": "Paris, France",
      "country_iso": "FR",
      "technology": "COBOL",
      "sector_hint": "Finance/Banque",
      "priority_boost": 25,
      "opportunity_type": "outsourcing_signal"
    }]
  }'

# Réponse :
{
  "ingested": 1,
  "skipped": 0,
  "total": 1
}
```

#### POST /api/classify

```bash
curl -X POST http://localhost:8000/api/classify \
  -H "X-API-Key: leadgen360_demo_secret_2024" \
  -H "Content-Type: application/json" \
  -d '{"text": "Appel d offres pour prestataire COBOL Mainframe en banque"}'

# Réponse :
{
  "sector_label": "Finance/Banque",
  "priority_label": "HIGH",
  "sector_confidence": 0.92,
  "priority_confidence": 0.88
}
```

#### GET /api/prospects

```bash
curl "http://localhost:8000/api/prospects?limit=5&min_score=80&country=FR" \
  -H "X-API-Key: leadgen360_demo_secret_2024"

# Réponse :
[
  {
    "id": "uuid-1",
    "company_name": "Crédit Mutuel",
    "opportunity_type": "b2b_tender",
    "technologies": ["COBOL"],
    "priority_score": 95,
    "country": "FR",
    "status": "new",
    "source_platform": "boamp",
    "created_at": "2026-05-02T10:30:00"
  },
  …
]
```

#### POST /api/generate/message

```bash
curl -X POST http://localhost:8000/api/generate/message \
  -H "X-API-Key: leadgen360_demo_secret_2024" \
  -H "Content-Type: application/json" \
  -d '{"opportunity_id": "uuid-de-lopportunite"}'

# Réponse :
{
  "message": "Bonjour [Prénom],\n\nJ'ai remarqué…",
  "lead_id": "uuid-du-lead-créé",
  "company_name": "Crédit Mutuel",
  "score": 95
}
```

#### POST /api/collect/all

```bash
curl -X POST http://localhost:8000/api/collect/all \
  -H "X-API-Key: leadgen360_demo_secret_2024"

# Réponse IMMÉDIATE (la collecte tourne en arrière-plan) :
{
  "status": "started",
  "message": "Collecte complète démarrée en arrière-plan"
}
```

---

## 8. Les 4 workflows n8n

n8n est un outil d'automatisation visuel (comme Zapier mais auto-hébergé sur votre serveur).  
**Accès** : `http://localhost:5678` — Login : `admin` / `admin123`

### Comment importer un workflow

```
1. Ouvrir http://localhost:5678
2. Menu hamburger (≡) en haut à gauche → "Workflows"
3. Bouton "+ New" → "Import from File"
4. Sélectionner le fichier .json dans n8n_workflows/
5. Sauvegarder (Ctrl+S)
6. Activer le workflow : toggle ON en haut à droite
```

---

### Workflow 01 — LinkedIn Hiring Signal Collector

**Fichier** : `n8n_workflows/01_linkedin_hiring.json`  
**Objectif** : déclencher la collecte LinkedIn toutes les 6 heures

#### Diagramme des nœuds

```
┌────────────────────────────────────────────────────────────────────────┐
│  WORKFLOW 01 — LinkedIn Hiring Signal Collector                         │
│                                                                          │
│  ┌─────────────────────┐     ┌──────────────────────────────────────┐  │
│  │  ⏰ Schedule Trigger │────▶│  🌐 HTTP Request                     │  │
│  │                      │     │                                      │  │
│  │  "Toutes les 6h"     │     │  POST http://api:8000/api/ingest     │  │
│  │  interval: 6 hours   │     │  Header: X-API-Key: {{$env.KEY}}     │  │
│  │                      │     │  Body: {"prospects": []}             │  │
│  └─────────────────────┘     └──────────────────────────────────────┘  │
│                                                                          │
│  Note: ce workflow est un déclencheur basique. La vraie collecte est    │
│  gérée par le workflow 04 plus complet.                                  │
└────────────────────────────────────────────────────────────────────────┘
```

#### Détail de chaque nœud

| Nœud | Type | Rôle | Paramètres clés |
|---|---|---|---|
| Toutes les 6h | Schedule Trigger | Déclenche toutes les 6h | interval: hours=6 |
| Déclencher collecte | HTTP Request | Appelle l'API | POST /api/ingest, X-API-Key header |

**Statut** : désactivé par défaut (le workflow 04 est plus complet et recommandé)

---

### Workflow 02 — BOAMP RSS Appels d'Offres IT

**Fichier** : `n8n_workflows/02_boamp_rss.json`  
**Objectif** : surveiller le flux RSS BOAMP, classifier chaque AO avec NLP

#### Diagramme des nœuds

```
┌────────────────────────────────────────────────────────────────────────────┐
│  WORKFLOW 02 — BOAMP RSS + Classification NLP                               │
│                                                                              │
│  ┌─────────────┐   ┌────────────────────┐   ┌──────────────┐   ┌────────┐ │
│  │ ⏰ Schedule  │──▶│ 🌐 HTTP Request     │──▶│ 📄 XML Node  │──▶│ 🌐 HTTP│ │
│  │             │   │                    │   │              │   │ Request│ │
│  │ Toutes      │   │ GET RSS BOAMP      │   │ Parse XML    │   │        │ │
│  │ les 12h     │   │ boamp.fr/avis/     │   │ → items[]    │   │ POST   │ │
│  │             │   │ flux-rss/?q=       │   │              │   │ /api/  │ │
│  │             │   │ informatique       │   │              │   │classify│ │
│  └─────────────┘   └────────────────────┘   └──────────────┘   └────────┘ │
│                                                                              │
│  Flux de données :                                                           │
│  Schedule → GET RSS → [item1, item2, ...] → pour chaque item:              │
│              POST /api/classify {"text": "{title} {description}"}           │
│              → {sector_label, priority_label, confidence}                   │
└────────────────────────────────────────────────────────────────────────────┘
```

#### Détail de chaque nœud

| Nœud | Type | Rôle | Paramètres clés |
|---|---|---|---|
| Toutes les 12h | Schedule Trigger | Déclencheur | interval: hours=12 |
| Récupérer RSS BOAMP | HTTP Request | GET flux RSS | URL: `boamp.fr/avis/flux-rss/?q=informatique` |
| Parser RSS XML | XML Node | Parse XML → JSON | dataPropertyName: "data" |
| Classifier appel d'offres | HTTP Request | NLP classify | POST /api/classify, body: title + description |

#### Ce que le workflow produit

```
Pour chaque appel d'offres BOAMP "informatique" :
  INPUT  → "{titre de l'AO} {description}"
  OUTPUT → {
    "sector_label": "Finance/Banque",
    "priority_label": "HIGH",
    "sector_confidence": 0.89
  }
```

---

### Workflow 03 — Live Demo Soutenance

**Fichier** : `n8n_workflows/03_live_demo.json`  
**Objectif** : démontrer le pipeline complet en une seule exécution manuelle  
**Cas d'usage** : présentation client, démo commerciale, soutenance

#### Diagramme des nœuds (pipeline complet)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  WORKFLOW 03 — Live Demo Soutenance (8 nœuds)                                 │
│                                                                                │
│  ┌────────┐  ┌─────────┐  ┌──────────┐  ┌──────┐  ┌─────────┐               │
│  │ ▶ Man. │─▶│ Set     │─▶│ POST     │─▶│ Wait │─▶│ GET     │               │
│  │ Trigger│  │ Params  │  │/api/     │  │ 3s   │  │/api/    │               │
│  │        │  │         │  │ingest    │  │      │  │prospects│               │
│  └────────┘  └─────────┘  └──────────┘  └──────┘  └────┬────┘               │
│                                                          │                    │
│  ┌────────────────────────────────────────────────────  │                    │
│  │                                                       ▼                    │
│  │  ┌─────────────┐  ┌─────────────────┐  ┌────────────────────────────┐   │
│  │  │ Résultat    │◀─│ POST /api/      │◀─│ Function: Extraire         │   │
│  │  │ Formaté     │  │ generate/message│  │ opportunity_id             │   │
│  │  │             │  │                 │  │ du premier prospect >=70   │   │
│  │  └─────────────┘  └─────────────────┘  └────────────────────────────┘   │
│  └────────────────────────────────────────────────────────────────────────  │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Détail complet de chaque nœud

**Nœud 1 — Démarrer la démo** (Manual Trigger)
```
Type : manualTrigger
Déclenchement : clic sur "Execute Workflow" dans n8n
Rôle : point d'entrée manuel du pipeline
```

**Nœud 2 — Paramètres de recherche** (Set)
```
Type : Set
Valeurs injectées :
  technology = "COBOL"
  location = "France"
  country_iso = "FR"
  limit = 10
  priority_boost = 25
Rôle : définir les variables utilisées par les nœuds suivants
```

**Nœud 3 — POST /api/ingest** (HTTP Request)
```
Type : HTTP Request
Méthode : POST
URL : http://leadgen_api:8000/api/ingest
Headers :
  X-API-Key: leadgen360_demo_secret_2024
  Content-Type: application/json
Body (JSON) :
{
  "prospects": [{
    "company_name": "BNP Paribas",
    "company_linkedin_url": "https://linkedin.com/company/bnp-paribas",
    "company_universal_name": "bnp-paribas",
    "job_title": "Développeur COBOL Senior",
    "job_url": "https://linkedin.com/jobs/view/demo-soutenance",
    "location": "Paris, France",
    "country_iso": "FR",
    "technology": "COBOL",
    "sector_hint": "Finance/Banque",
    "priority_boost": 25,
    "raw_job": {}
  }]
}
Rôle : injecter un prospect COBOL de démo en DB
```

**Nœud 4 — Attente 3s** (Wait)
```
Type : Wait
Durée : 3 secondes
Rôle : laisser le temps à la DB d'indexer l'opportunité
```

**Nœud 5 — GET top prospects** (HTTP Request)
```
Type : HTTP Request
Méthode : GET
URL : http://leadgen_api:8000/api/prospects
Headers :
  X-API-Key: leadgen360_demo_secret_2024
Query params :
  min_score = 70
  limit = 5
Rôle : récupérer les meilleurs prospects pour choisir celui à démontrer
```

**Nœud 6 — Extraire opportunity_id** (Function)
```
Type : Function (JavaScript)
Code :
  const list = Array.isArray(data) ? data : [data];
  if (list.length === 0) throw new Error('Aucun prospect >= 70');
  const first = list[0];
  return [{json: {
    opportunity_id: first.id,
    company_name: first.company_name,
    score: first.priority_score,
    technology: first.technologies?.[0] ?? 'IT',
    country: first.country
  }}];
Rôle : extraire l'ID UUID du meilleur prospect pour la génération de message
```

**Nœud 7 — POST /api/generate/message** (HTTP Request)
```
Type : HTTP Request
Méthode : POST
URL : http://leadgen_api:8000/api/generate/message
Headers :
  X-API-Key: leadgen360_demo_secret_2024
  Content-Type: application/json
Body :
  {"opportunity_id": "{{ $json.opportunity_id }}"}
Rôle : appeler Groq LLM pour générer le message LinkedIn
Latence attendue : 1-3 secondes
```

**Nœud 8 — Résultat formaté** (Set)
```
Type : Set
Valeurs mappées :
  entreprise        = {{ $json.company_name }}
  score             = {{ $json.score }}/100
  message_linkedin  = {{ $json.message }}
  lead_id           = {{ $json.lead_id }}
  status            = "success — LeadGen 360+ Solvinya Group"
Rôle : formater la sortie finale pour la présentation
```

#### Résultat visible dans n8n après exécution

```
{
  "entreprise": "BNP Paribas",
  "score": "95/100",
  "message_linkedin": "Bonjour [Prénom],\n\nJ'ai remarqué que BNP Paribas recrute activement des profils COBOL…",
  "lead_id": "a4f2c8d1-…",
  "status": "success — LeadGen 360+ Solvinya Group"
}
```

---

### Workflow 04 — Déclencheur Collecte Automatique (Principal)

**Fichier** : `n8n_workflows/04_collect_trigger.json`  
**Objectif** : déclencher la collecte complète toutes les 12 heures ET permettre un déclenchement manuel via webhook  
**C'est le workflow de production principal.**

#### Diagramme des nœuds

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  WORKFLOW 04 — Déclencheur Collecte (6 nœuds)                                 │
│                                                                                │
│  ┌─────────────┐                                                               │
│  │ ⏰ Schedule  │─────────────────────┐                                        │
│  │ Toutes 12h  │                     │                                        │
│  └─────────────┘                     ▼                                        │
│                              ┌───────────────────┐                            │
│  ┌─────────────┐             │ 🌐 HTTP Request    │                            │
│  │ 🔗 Webhook  │────────────▶│                   │                            │
│  │ /webhook/   │             │ POST              │                            │
│  │ collect     │             │ http://leadgen_   │                            │
│  │ (manuel)    │             │ api:8000/api/     │                            │
│  └─────────────┘             │ collect/all       │                            │
│                              │ X-API-Key: …      │                            │
│                              │ timeout: 10s      │                            │
│                              └────────┬──────────┘                            │
│                                       │                                        │
│                                       ▼                                        │
│                              ┌───────────────────┐                            │
│                              │  ❓ IF             │                            │
│                              │  status == "started"│                          │
│                              └──────┬────────────┘                            │
│                                     │                                          │
│               ┌─────────────────────┴──────────────────────┐                  │
│               ▼ TRUE                                        ▼ FALSE            │
│     ┌─────────────────────┐                    ┌───────────────────────┐      │
│     │ 💻 Code: Formater   │                    │ 💻 Code: Formater     │      │
│     │    succès           │                    │    erreur             │      │
│     │                     │                    │                       │      │
│     │ timestamp, status,  │                    │ timestamp, status,    │      │
│     │ message, source     │                    │ details               │      │
│     └─────────────────────┘                    └───────────────────────┘      │
└──────────────────────────────────────────────────────────────────────────────┘
```

#### Détail complet de chaque nœud

**Nœud 1 — Toutes les 12h** (Schedule Trigger)
```
Type : scheduleTrigger
interval : hours=12
Déclenchement : automatique toutes les 12h
Connexion vers : "Déclencher collecte complète"
```

**Nœud 2 — Webhook manuel** (Webhook)
```
Type : webhook
httpMethod : POST
path : collect
→ URL complète : http://localhost:5678/webhook/collect
responseMode : lastNode (retourne la réponse du dernier nœud)
Connexion vers : "Déclencher collecte complète"
Utilisation :
  curl -X POST http://localhost:5678/webhook/collect
```

**Nœud 3 — Déclencher collecte complète** (HTTP Request)
```
Type : HTTP Request
Méthode : POST
URL : http://leadgen_api:8000/api/collect/all
Headers :
  X-API-Key: leadgen360_demo_secret_2024
  Content-Type: application/json
Options :
  timeout: 10000 (10 secondes — l'API répond vite, la collecte tourne en fond)
Connexion vers : "Collecte démarrée ?"
```

**Nœud 4 — Collecte démarrée ?** (IF)
```
Type : if
Condition : $json.status == "started"
Branche TRUE  → "Formater succès"
Branche FALSE → "Formater erreur"
```

**Nœud 5 — Formater succès** (Code JavaScript)
```javascript
return [{json: {
  timestamp: new Date().toISOString(),
  status: 'started',
  message: $input.item.json.message,
  source: 'n8n-scheduled'
}}];
```

**Nœud 6 — Formater erreur** (Code JavaScript)
```javascript
return [{json: {
  timestamp: new Date().toISOString(),
  status: 'error',
  details: $input.item.json
}}];
```

#### Flux de données complet

```
DÉCLENCHEMENT (schedule ou webhook)
         │
         ▼
POST http://leadgen_api:8000/api/collect/all
  Header: X-API-Key: leadgen360_demo_secret_2024
         │
         ▼ (réponse en ~200ms)
  {"status": "started", "message": "Collecte complète démarrée en arrière-plan"}
         │
         ▼
IF status == "started" ?
         │
    TRUE │                   FALSE │
         ▼                         ▼
  {timestamp, status=started,  {timestamp, status=error, details}
   message, source=n8n}         → loggé dans n8n pour diagnostic
         │
         │
(Pendant ce temps, en arrière-plan dans FastAPI :)
         │
         ▼
  collectors/run_all.py → linkedin_b2b → boamp → ted → linkedin
  Durée totale : 15-45 minutes selon le nombre de comptes et la vitesse réseau
  Résultats : loggés dans docker compose logs api
```

---

## 9. Base de données PostgreSQL

### 9.1 Schéma complet

```sql
-- ── Table principale des entreprises ──────────────────────────────────────────
CREATE TABLE companies (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(255) NOT NULL,
    linkedin_url VARCHAR(500) UNIQUE,   -- clé de déduplication
    country      CHAR(2),
    sector       VARCHAR(80),
    source       VARCHAR(50),
    raw_data     JSONB,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ── Table des opportunités détectées ─────────────────────────────────────────
CREATE TABLE opportunities (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id       UUID REFERENCES companies(id) ON DELETE CASCADE,
    title            VARCHAR(500),
    description      TEXT,
    opportunity_type VARCHAR(50),         -- b2b_tender / b2b_rfp / outsourcing_signal / ...
    technologies     TEXT[],              -- array: ["COBOL", "Java"]
    source_url       VARCHAR(1000),
    source_platform  VARCHAR(80),         -- boamp / ted / linkedin_jobs / linkedin_b2b / codeur / twago
    country          CHAR(2),
    priority_score   SMALLINT,            -- 0-100
    sector_label     VARCHAR(80),
    status           VARCHAR(30) DEFAULT 'new',  -- new/qualified/contacted/converted/rejected
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ── Table des contacts ────────────────────────────────────────────────────────
CREATE TABLE contacts (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id        UUID REFERENCES companies(id),
    full_name         VARCHAR(200),
    job_title         VARCHAR(200),
    email             VARCHAR(200),
    linkedin_url      VARCHAR(500),
    is_decision_maker BOOLEAN DEFAULT FALSE,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- ── Table des leads (messages générés) ───────────────────────────────────────
CREATE TABLE leads (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id        UUID REFERENCES opportunities(id),
    contact_id            UUID REFERENCES contacts(id),
    generated_linkedin_msg TEXT,
    generated_email        TEXT,
    status                VARCHAR(30) DEFAULT 'draft',  -- draft/sent/responded/converted
    sent_at               TIMESTAMPTZ,
    responded_at          TIMESTAMPTZ,
    notes                 TEXT,
    created_at            TIMESTAMPTZ DEFAULT NOW()
);

-- ── Index pour les performances ───────────────────────────────────────────────
CREATE INDEX idx_opp_score   ON opportunities(priority_score DESC);
CREATE INDEX idx_opp_status  ON opportunities(status);
CREATE INDEX idx_opp_country ON opportunities(country);
CREATE INDEX idx_opp_type    ON opportunities(opportunity_type);
CREATE INDEX idx_opp_company ON opportunities(company_id);
CREATE INDEX idx_opp_created ON opportunities(created_at DESC);
```

### 9.2 Requêtes utiles

```sql
-- Top 20 prospects par score (pour le commercial)
SELECT c.name, o.opportunity_type, o.source_platform,
       o.country, o.priority_score, o.technologies[1] as tech,
       o.created_at
FROM opportunities o
JOIN companies c ON c.id = o.company_id
WHERE o.status = 'new'
ORDER BY o.priority_score DESC
LIMIT 20;

-- Répartition par source et type (stats journalières)
SELECT source_platform, opportunity_type, country,
       count(*) as total, round(avg(priority_score)) as avg_score
FROM opportunities
GROUP BY source_platform, opportunity_type, country
ORDER BY total DESC;

-- Prospects haute priorité non contactés
SELECT c.name, o.opportunity_type, o.technologies,
       o.priority_score, o.source_platform
FROM opportunities o
JOIN companies c ON c.id = o.company_id
WHERE o.priority_score >= 80 AND o.status = 'new'
ORDER BY o.priority_score DESC;

-- Doublons résiduels (audit)
SELECT company_id, technologies[1], opportunity_type, count(*)
FROM opportunities
GROUP BY company_id, technologies[1], opportunity_type
HAVING count(*) > 1;

-- Volume collecté par jour
SELECT date_trunc('day', created_at) as jour,
       source_platform, count(*) as nb
FROM opportunities
GROUP BY jour, source_platform
ORDER BY jour DESC;
```

---

## 10. Dashboard Metabase

**Accès** : `http://localhost:3000`

### Première configuration

```
1. Ouvrir http://localhost:3000
2. Cliquer "Let's get started"
3. Créer un compte admin (email + mot de passe)
4. "Add your data" → choisir PostgreSQL
5. Remplir :
   Host     : postgres          (nom du service Docker, PAS localhost)
   Port     : 5432
   Database : leadgen360
   Username : leadgen
   Password : leadgen_secret    (celle de votre .env)
6. "Test connection" → doit afficher "Connected successfully"
7. Terminer l'assistant
```

### Tableaux de bord recommandés

**Dashboard 1 : Vue commerciale**
```
Question 1 : "Top 20 prospects — score >= 80"
  → Tableau : nom entreprise | type signal | tech | pays | score | source

Question 2 : "Répartition par source"
  → Graphe barres : boamp(236) | ted(422) | linkedin_jobs(157) | linkedin_b2b(?)

Question 3 : "Score moyen par pays"
  → Graphe barres : LU=66 | CH=65 | BE=63 | FR=65

Question 4 : "Évolution quotidienne des collectes"
  → Graphe ligne : volume par jour et par source
```

**Dashboard 2 : Suivi pipeline commercial**
```
Question 5 : "Funnel de conversion"
  → Entonnoir : new | qualified | contacted | converted

Question 6 : "Prospects haute valeur non encore contactés"
  → Alertes : score >= 85 ET status = 'new' ET created_at > NOW() - 7 jours
```

---

## 11. Installation sur un nouveau PC

### Prérequis

| Logiciel | Version | Téléchargement |
|---|---|---|
| Docker Desktop | 4.x+ | https://docker.com/products/docker-desktop |
| Python | 3.10 ou 3.11 | https://python.org/downloads |
| Git | n'importe | https://git-scm.com |

> **Windows** : lors de l'installation de Docker Desktop, accepter d'activer WSL2 si demandé. Redémarrer si nécessaire.

---

### Étape 1 — Copier le projet

```bash
# Option A : copier le dossier depuis l'ancien PC
# → copier C:\personal\scrapping\leadgen360 vers le même chemin

# Option B : depuis un dépôt Git
git clone <url-repo> leadgen360
cd leadgen360
```

---

### Étape 2 — Créer le fichier .env

```bash
cp .env.example .env
```

Éditer `.env` avec ces valeurs (remplacer par les vôtres) :

```env
# ── Base de données ─────────────────────────────────────────────
POSTGRES_USER=leadgen
POSTGRES_PASSWORD=leadgen_secret
POSTGRES_DB=leadgen360
DATABASE_URL=postgresql://leadgen:leadgen_secret@postgres:5432/leadgen360

# ── API ─────────────────────────────────────────────────────────
API_SECRET_KEY=leadgen360_demo_secret_2024

# ── LinkedIn (mettre 2-3 comptes pour la rotation) ─────────────
LINKEDIN_EMAIL_1=votre_email1@gmail.com
LINKEDIN_PASSWORD_1=votre_mot_de_passe_1
LINKEDIN_EMAIL_2=votre_email2@gmail.com
LINKEDIN_PASSWORD_2=votre_mot_de_passe_2

# ── LLM (gratuit sur console.groq.com) ─────────────────────────
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxx
GROQ_MODEL=llama-3.1-8b-instant

# ── Enrichissement email (optionnel) ────────────────────────────
HUNTER_API_KEY=

# ── n8n ─────────────────────────────────────────────────────────
N8N_USER=admin
N8N_PASSWORD=admin123
```

---

### Étape 3 — Installer les dépendances Python

```bash
# Créer l'environnement virtuel
python -m venv .venv

# Activer (Windows)
.venv\Scripts\activate

# Activer (Mac/Linux)
source .venv/bin/activate

# Installer toutes les dépendances
pip install fastapi uvicorn asyncpg pydantic pydantic-settings \
            python-dotenv linkedin-api httpx tenacity \
            scikit-learn numpy scipy joblib loguru \
            matplotlib sentence-transformers \
            python-jose python-multipart aiofiles \
            pytest pytest-asyncio
```

---

### Étape 4 — Démarrer les services Docker

```bash
# Démarrer tous les services
docker compose up -d

# Vérifier que tout tourne (attendre ~60s la première fois)
docker compose ps
```

Résultat attendu :
```
NAME               STATUS          PORTS
leadgen_api        Up (healthy)    0.0.0.0:8000->8000/tcp
leadgen_metabase   Up              0.0.0.0:3000->3000/tcp
leadgen_n8n        Up              0.0.0.0:5678->5678/tcp
leadgen_postgres   Up (healthy)    0.0.0.0:5432->5432/tcp
leadgen_redis      Up (healthy)    0.0.0.0:6379->6379/tcp
```

> **Première fois** : Docker télécharge les images (~2-3 Go). Prévoir 5-10 minutes selon la connexion.

---

### Étape 5 — Vérifier l'API

```bash
curl http://localhost:8000/health
# Attendu : {"status":"ok","database":"ok","service":"leadgen360-api","version":"1.0.0"}
```

---

### Étape 6 — Entraîner le modèle NLP

```bash
# Dans le venv activé
LEADGEN_USE_TFIDF=1 python -m nlp.trainer

# Attendu :
# Cross-val 75.0% >= 75%. Modeles prets pour la production.
```

---

### Étape 7 — Première collecte (test)

```bash
# Test BOAMP sans écriture DB (recommandé pour vérifier que tout fonctionne)
docker compose exec api python -m collectors.run_all --dry-run --source boamp

# Si OK → collecte réelle BOAMP
docker compose exec api python -m collectors.run_all --source boamp

# Collecte TED (marchés publics EU)
docker compose exec api python -m collectors.run_all --source ted

# Vérifier les résultats
docker compose exec postgres psql -U leadgen -d leadgen360 -c "SELECT country, sector_label, count(*), round(avg(priority_score)) as avg_score FROM opportunities GROUP BY country, sector_label ORDER BY count DESC;"
```

---

### Étape 8 — Importer les workflows n8n

```
1. Ouvrir http://localhost:5678
2. Créer un compte admin (email + mot de passe n'importe lequel)
3. Workflow 04 (le plus important) :
   Menu ≡ → Workflows → + New → Import from File
   → Sélectionner n8n_workflows/04_collect_trigger.json
   → Save → Activer le toggle ON
4. Importer aussi 03_live_demo.json pour les démos
```

---

### Étape 9 — Configurer Metabase

```
1. Ouvrir http://localhost:3000
2. Créer un compte admin
3. Add data → PostgreSQL
   Host: postgres (PAS localhost — c'est le nom Docker)
   Port: 5432
   Database: leadgen360
   User: leadgen
   Password: leadgen_secret
4. Terminer la configuration
```

---

### Dépannage fréquent

| Problème | Cause probable | Solution |
|---|---|---|
| `role "leadgen" does not exist` | Volume PostgreSQL d'un ancien état | `docker volume rm leadgen360_postgres_data` puis `docker compose up -d` |
| `No module named 'numpy'` | Venv non activé ou pip incomplet | `source .venv/bin/activate && pip install numpy scipy scikit-learn` |
| LinkedIn `CHALLENGE_REQUIRED` | Vérification humaine demandée | Se connecter manuellement sur linkedin.com depuis le navigateur, puis réessayer |
| `Groq 400` | Modèle déprécié ou mauvais model ID | Vérifier `GROQ_MODEL=llama-3.1-8b-instant` dans `.env` |
| Codeur/Twago retourne 0 | Site a changé sa structure HTML | Vérifier les patterns regex dans `_parse_html()` — le site peut avoir redesigné ses blocs projet |
| API ne démarre pas | Code mis à jour, image obsolète | `docker compose build api && docker compose up -d api` |
| n8n ne joind pas l'API | URL Docker incorrecte | Utiliser `http://leadgen_api:8000` (pas `localhost`) dans n8n |
| Metabase DB refused | Host incorrect | Mettre `postgres` comme Host (pas `localhost`) |

---

## 12. Démonstrations pas-à-pas

### Demo 1 — Collecte BOAMP + TED (sans LinkedIn, ~5 min)

```bash
# 1. S'assurer que les services tournent
docker compose up -d
curl http://localhost:8000/health && docker compose ps

# 2. Test BOAMP — aperçu sans écrire en DB
docker compose exec api python -m collectors.run_all --dry-run --source boamp
# → affiche les marchés publics IT détectés

# 3. Collecte BOAMP réelle
docker compose exec api python -m collectors.run_all --source boamp
# → attendu : ~215-236 prospects ingérés

# 4. Collecte TED — marchés publics EU
docker compose exec api python -m collectors.run_all --source ted
# → attendu : ~422 prospects (FR+BE+LU+CH)

# 5. Voir les résultats
docker compose exec postgres psql -U leadgen -d leadgen360 -c "SELECT country, sector_label, count(*), round(avg(priority_score)) as avg_score FROM opportunities GROUP BY country, sector_label ORDER BY count DESC;"
# Résultat attendu :
# b2b_tender / boamp / FR  : 236 prospects, score moyen 66
# b2b_tender / ted   / FR  : 145 prospects
# b2b_tender / ted   / BE  : 105 prospects
# b2b_tender / ted   / CH  :  98 prospects
# b2b_tender / ted   / LU  :  74 prospects
```

---

### Demo 2 — Signal LinkedIn + génération de message (~10 min)

```bash
# 1. Collecte LinkedIn (offres emploi IT → outsourcing_signal)
docker compose exec api python -m collectors.run_all --dry-run --source linkedin    # Vérifier sans écrire
docker compose exec api python -m collectors.run_all --source linkedin               # Collecter pour de vrai

# 2. Injecter manuellement un prospect COBOL de démo
curl -X POST http://localhost:8000/api/ingest \
  -H "X-API-Key: leadgen360_demo_secret_2024" \
  -H "Content-Type: application/json" \
  -d '{
    "prospects": [{
      "company_name": "Société Générale",
      "company_linkedin_url": "https://linkedin.com/company/societe-generale",
      "company_universal_name": "societe-generale",
      "job_title": "Développeur COBOL Senior",
      "job_url": "https://linkedin.com/jobs/view/123456",
      "location": "Paris, France",
      "country_iso": "FR",
      "technology": "COBOL",
      "sector_hint": "Finance/Banque",
      "priority_boost": 25,
      "opportunity_type": "outsourcing_signal"
    }]
  }'
# → {"ingested": 1, "skipped": 0, "total": 1}

# 3. Récupérer les meilleurs prospects
curl "http://localhost:8000/api/prospects?min_score=80&limit=5" \
  -H "X-API-Key: leadgen360_demo_secret_2024"
# → noter l'id de Société Générale

# 4. Générer le message LinkedIn
curl -X POST http://localhost:8000/api/generate/message \
  -H "X-API-Key: leadgen360_demo_secret_2024" \
  -H "Content-Type: application/json" \
  -d '{"opportunity_id": "<id-copié-à-létape-3>"}'

# → message LinkedIn personnalisé en 5 lignes, prêt à envoyer
```

---

### Demo 3 — Workflow n8n live (pipeline complet ~2 min)

```
1. Ouvrir http://localhost:5678
2. Aller dans Workflows → "03 — Live Demo Soutenance"
3. Cliquer "Execute Workflow" (bouton ▶)
4. Observer les nœuds s'allumer un par un :
   ✓ Manual Trigger
   ✓ Paramètres de recherche (COBOL, France)
   ✓ POST /api/ingest → BNP Paribas ingéré
   ✓ Wait 3s
   ✓ GET /api/prospects → top 5 >= 70
   ✓ Extraire opportunity_id
   ✓ POST /api/generate/message → Groq LLM appelé
   ✓ Résultat formaté

5. Cliquer sur "Résultat formaté" pour voir :
   {
     "entreprise": "BNP Paribas",
     "score": "95/100",
     "message_linkedin": "Bonjour [Prénom],\n\nJ'ai remarqué que BNP Paribas recrute…",
     "status": "success — LeadGen 360+ Solvinya Group"
   }
```

---

### Demo 4 — NLP Classify

```bash
# Classifier un texte d'appel d'offres
curl -X POST http://localhost:8000/api/classify \
  -H "X-API-Key: leadgen360_demo_secret_2024" \
  -H "Content-Type: application/json" \
  -d '{"text": "Appel d offres pour prestataire COBOL Mainframe systeme bancaire"}'

# Résultat :
{
  "sector_label": "Finance/Banque",
  "priority_label": "HIGH",
  "sector_confidence": 0.92,
  "priority_confidence": 0.88
}

# Autre exemple — secteur public
curl -X POST http://localhost:8000/api/classify \
  -H "X-API-Key: leadgen360_demo_secret_2024" \
  -H "Content-Type: application/json" \
  -d '{"text": "Marche public developpement application web mairie"}'

# Résultat :
{
  "sector_label": "Secteur public",
  "priority_label": "MEDIUM",
  "sector_confidence": 0.78,
  "priority_confidence": 0.82
}
```

---

### Demo 5 — Déclenchement collecte via webhook n8n

```bash
# Déclencher manuellement la collecte complète via n8n
curl -X POST http://localhost:5678/webhook/collect \
  -H "Content-Type: application/json" \
  -d '{}'

# Le workflow 04 reçoit l'appel → appelle POST /api/collect/all
# L'API démarre la collecte en arrière-plan
# Suivre les logs :
docker compose logs -f api | grep -E "INFO|SUCCESS|WARNING|ERROR"
```

---

## 13. Référence des commandes

```bash
# ── Services Docker ──────────────────────────────────────────────────────────
docker compose up -d                                      # Démarrer tous les services
docker compose down                                       # Arrêter tous les services
docker compose logs -f api                                # Logs temps réel de l'API
curl http://localhost:8000/health && docker compose ps    # curl /health + statut services
docker compose build api && docker compose up -d api      # Reconstruire l'image API (après modif Python)

# ── Collecte ─────────────────────────────────────────────────────────────────
docker compose exec api python -m collectors.run_all                              # Collecte complète
docker compose exec api python -m collectors.run_all --dry-run                    # Simulation sans écriture DB
docker compose exec api python -m collectors.run_all --source linkedin            # LinkedIn Jobs uniquement
docker compose exec api python -m collectors.run_all --dry-run --source linkedin  # LinkedIn Jobs — dry run
docker compose exec api python -m collectors.run_all --source linkedin_b2b        # LinkedIn Posts B2B
docker compose exec api python -m collectors.run_all --dry-run --source linkedin_b2b  # LinkedIn B2B — dry run
docker compose exec api python -m collectors.run_all --source boamp              # BOAMP (marchés publics France)
docker compose exec api python -m collectors.run_all --dry-run --source boamp    # BOAMP — dry run
docker compose exec api python -m collectors.run_all --source ted                # TED EU (FR/BE/LU/CH)
docker compose exec api python -m collectors.run_all --dry-run --source ted      # TED — dry run
docker compose exec api python -m collectors.run_all --source codeur             # Codeur.com (missions freelance France)
docker compose exec api python -m collectors.run_all --dry-run --source codeur   # Codeur — dry run
docker compose exec api python -m collectors.run_all --source twago              # TwagoFreelance.com (missions FR/BE/CH)
docker compose exec api python -m collectors.run_all --dry-run --source twago    # Twago — dry run

# ── API (déclenchement HTTP) ─────────────────────────────────────────────────
curl -X POST http://localhost:8000/api/collect/all -H "X-API-Key: leadgen360_demo_secret_2024"      # POST /api/collect/all
curl -X POST http://localhost:8000/api/collect/linkedin -H "X-API-Key: leadgen360_demo_secret_2024" # POST /api/collect/linkedin

# ── NLP ──────────────────────────────────────────────────────────────────────
docker compose exec api python -m nlp.trainer            # Entraîner les modèles NLP

# ── Base de données ──────────────────────────────────────────────────────────
docker compose exec postgres psql -U leadgen -d leadgen360   # Shell psql interactif
docker compose exec postgres psql -U leadgen -d leadgen360 -c "SELECT country, sector_label, count(*), round(avg(priority_score)) as avg_score FROM opportunities GROUP BY country, sector_label ORDER BY count DESC;"  # Stats

# ── Tests ────────────────────────────────────────────────────────────────────
docker compose exec api pytest tests/ -v --tb=short      # pytest (tests API, NLP, pipeline)
```

---

## 14. Résultats actuels

### Volume de données (au 2 mai 2026)

```
Source          Pays   Prospects   Score moyen   Type de signal
─────────────── ────── ─────────── ────────────  ─────────────────────
BOAMP           FR     236          66            b2b_tender
TED             FR     145          65            b2b_tender
TED             BE     105          63            b2b_tender
TED             CH      98          65            b2b_tender
TED             LU      74          66            b2b_tender
LinkedIn Jobs   FR     122          79            outsourcing_signal
LinkedIn Jobs   BE      12          83            outsourcing_signal
LinkedIn Jobs   TN      11          75            outsourcing_signal
LinkedIn Jobs   LU      10          84            outsourcing_signal
LinkedIn Jobs   CH       2          87            outsourcing_signal
─────────────── ────── ─────────── ────────────  ─────────────────────
TOTAL                  815
```

### Répartition par priorité

```
Score 80-100  ████████████░░░░░░░░  ~158 prospects  (LU/CH + COBOL/SAP)
Score 60-79   ████████████████████  ~387 prospects
Score  0-59   ████████░░░░░░░░░░░░  ~270 prospects
```

### Pipeline de traitement complet

```
Source externe
    │  Délai API/scraping : 0.3s (BOAMP) à 2s (LinkedIn)
    ▼
Collecteur Python
    │  Délai normalisation : < 5ms
    ▼
pipeline/ingest.py
    │  Upsert + dédup + scoring : ~50ms (asyncpg)
    ▼
PostgreSQL (stocké, indexé)
    │
    │  Sur demande du commercial :
    ▼
POST /api/classify          → NLP sector + priority  : ~100ms
    ▼
POST /api/generate/message  → LLM Groq                : 1-3s
    ▼
Message LinkedIn prêt à envoyer
```

---

## 15. Structure complète des fichiers

```
leadgen360/
│
├── api/
│   ├── Dockerfile              # Image Python 3.11-slim + dépendances
│   ├── main.py                 # FastAPI app : lifecycle, CORS, routers
│   ├── auth.py                 # Middleware X-API-Key
│   └── routes/
│       ├── health.py           # GET /health → DB ping
│       ├── ingest.py           # POST /api/ingest → ingest_raw_dict()
│       ├── classify.py         # POST /api/classify → OpportunityClassifier
│       ├── generate.py         # POST /api/generate/message + /email
│       ├── prospects.py        # GET /api/prospects (pagination, filtres)
│       └── collect.py          # POST /api/collect/* → BackgroundTasks
│
├── collectors/
│   ├── base.py                 # BaseCollector : log_start(), log_done()
│   ├── linkedin_hiring.py      # LinkedIn Jobs → outsourcing_signal
│   ├── linkedin_b2b.py         # LinkedIn Posts → b2b_* (regex scoring)
│   ├── linkedin_client.py      # Wrapper async linkedin-api (unofficial)
│   ├── session_manager.py      # Pool de comptes LinkedIn, rotation
│   ├── boamp.py                # API BOAMP open data
│   ├── ted.py                  # API TED EU (POST expert query)
│   ├── codeur.py               # Codeur.com (missions freelance IT France)
│   ├── twago.py                # TwagoFreelance.com (missions IT FR/BE/CH)
│   └── run_all.py              # Orchestrateur CLI (argparse --source)
│
├── pipeline/
│   ├── ingest.py               # Upsert, dédup 30j, scoring, INSERT
│   ├── scorer_rules.py         # compute_rule_score() : pays+tech+secteur+boost
│   └── enricher.py             # Hunter.io : email lookup (optionnel)
│
├── nlp/
│   ├── classifier.py           # OpportunityClassifier : TF-IDF + LinearSVC
│   ├── trainer.py              # Entraînement + validation 75% CV
│   ├── evaluator.py            # Métriques, confusion matrix, rapport JSON
│   ├── data/
│   │   └── training_data.py    # 604 exemples labelisés (secteur + priorité)
│   ├── models/                 # sector_model.joblib, priority_model.joblib
│   └── reports/                # evaluation_summary.json
│
├── automation/
│   ├── llm_client.py           # Groq API + Ollama fallback
│   ├── message_generator.py    # Prompt LinkedIn adapté au type de signal
│   └── email_generator.py      # Prompt email (objet + corps)
│
├── db/
│   ├── init.sql                # CREATE TABLE + INDEX + triggers updated_at
│   ├── client.py               # Pool asyncpg partagé (singleton)
│   └── queries/                # Requêtes SQL nommées
│
├── config/
│   └── settings.py             # Pydantic BaseSettings → .env
│
├── n8n_workflows/
│   ├── 01_linkedin_hiring.json # Schedule 6h → POST /api/ingest
│   ├── 02_boamp_rss.json       # Schedule 12h → GET RSS → classify NLP
│   ├── 03_live_demo.json       # Demo bout-en-bout : ingest → classify → generate
│   └── 04_collect_trigger.json # Schedule 12h + Webhook → POST /api/collect/all
│
├── tests/
│   ├── test_api.py             # Tests endpoints FastAPI (pytest-asyncio)
│   ├── test_nlp.py             # Tests classifier (accuracy >= 70%)
│   └── test_pipeline.py        # Tests ingest + scoring
│
├── .env                        # Variables d'environnement (NE PAS committer)
├── .env.example                # Template avec toutes les variables commentées
├── docker-compose.yml          # 5 services : postgres, redis, n8n, metabase, api
├── Makefile                    # Référence des commandes (voir section 13 pour les équivalents directs)
└── pyproject.toml              # Métadonnées Python + dépendances
```

---

*Documentation complète — LeadGen Francophone 360+ v1.0 — Solvinya Group — Mai 2026*
