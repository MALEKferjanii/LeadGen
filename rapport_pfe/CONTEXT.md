# Rapport PFE — LeadGen Francophone 360+ — Contexte de session

> Fichier de contexte généré le 2026-05-04 pour accélérer les futures sessions Claude.
> Projet : `C:/personal/scrapping/rapport_pfe/`

---

## Résumé du projet

Rapport de fin d'études (PFE) rédigé en LaTeX suivant le template ESPRIT pour le projet
**LeadGen Francophone 360+** développé chez **Solvinya Group** (Ferjani Malek, mai 2026).

---

## Structure des fichiers

```
rapport_pfe/
├── Main.tex          ← Fichier principal (preamble + \include)
├── garde_fin.tex     ← Couverture TikZ (bandes bleues/rouge ESPRIT)
├── form.tex          ← Formulaire validation encadrants
├── Dedicaces.tex
├── Remerciements.tex
├── Introduction.tex
├── Chapter1.tex      ← Cadre du projet (Solvinya, signaux, Scrum)
├── Chapter2.tex      ← Analyse des besoins + Architecture macro
├── Chapter3.tex      ← Conception technique (collecteurs, pipeline, NLP, n8n)
├── Chapter4.tex      ← Réalisation et résultats (815 prospects)
├── Conclusion.tex
├── bibliography.bib  ← 11 références BibTeX (aucun \cite dans le doc)
├── garde_fin2.tex    ← 4e de couverture (Résumé FR + Abstract EN)
└── Main.pdf          ← PDF compilé (47 pages, ~770 KB)
```

---

## Compilation locale

**MiKTeX 24.1** installé sur Windows 11 à :
`C:\Users\Malek.Ferjani\AppData\Local\Programs\MiKTeX\miktex\bin\x64\`

```bash
cd C:/personal/scrapping/rapport_pfe
pdflatex -interaction=nonstopmode Main.tex   # passe 1
bibtex Main                                  # (aucune citation → erreur normale)
pdflatex -interaction=nonstopmode Main.tex   # passe 2
pdflatex -interaction=nonstopmode Main.tex   # passe 3 (stable : 47 pages)
```

**Note MiKTeX** : si erreurs `\ar@align@mcell` (array v2.5g trop vieux), lancer d'abord :
```bash
miktex packages update
```

---

## Couleurs définies dans Main.tex

| Commande | RGB | Usage |
|---|---|---|
| `espritBlue` | 0,84,159 | Titres, headers, liens |
| `espritRed` | 196,30,58 | Alertes, accents |
| `espritGray` | 88,88,88 | Texte secondaire |
| `lightBlue` | 230,241,251 | Fond infobox |
| `lightGreen` | 225,245,238 | Fond successbox |
| `lightAmber` | 250,238,218 | Fond warningbox |
| `darkGreen` | 8,80,65 | Collecteurs LinkedIn |
| `darkBlue` | 12,68,124 | Pipeline |
| `colColor` | = lightGreen | Nœuds collecteurs TikZ |
| `pipColor` | = lightBlue | Nœuds pipeline TikZ |
| `nlpColor` | = lightAmber | Nœuds NLP TikZ |
| `warnColor` | 252,235,235 | Nœuds warning/inactifs TikZ |

---

## Environnements tcolorbox

Définis dans Main.tex — argument optionnel `[#1]` = titre, PAS de virgule dans le titre !

```latex
\begin{infobox}[Titre sans virgule]   % fond bleu
\begin{warningbox}[Titre]             % fond ambre
\begin{successbox}[Titre sans virgule] % fond vert
```

Si virgule dans le titre → utiliser `[{Titre, avec virgule}]` ou supprimer les virgules.

---

## Règles TikZ critiques (bugs corrigés)

### 1. Styles TikZ paramétrés — PAS d'`!` dans l'argument
```latex
% CASSÉ : box/.style={draw=#1!70} appelé avec \node[box=darkGreen!40]
%         → produce draw=darkGreen!40!70 → xcolor error "Undefined color '70'"
% OK    : \node[box=espritBlue] (argument sans '!')
%         OU définir des styles explicites nommés (srcbox, colbox, etc.)
```

### 2. Style nommé `step` — conflit avec TikZ built-in
```latex
% CASSÉ : step/.style={...}  ← TikZ utilise 'step' pour les grilles
% OK    : pipstep/.style={...}
```

### 3. `\\` dans nœud TikZ sans `align`
```latex
% CASSÉ : \node[font=\scriptsize] {Ligne1\\Ligne2};  → "Not allowed in LR mode"
% OK    : \node[font=\scriptsize, align=center] {Ligne1\\Ligne2};
```

### 4. `\foreach \a/\b in {liste}` — le `/` dans les valeurs casse le split
```latex
% CASSÉ : \foreach \txt/\lat in {pipeline/ingest.py/50ms, ...}
% OK    : nœuds manuels explicites \node[...] (s0) at (0,0) {...};
```

---

## Règles pgfplots critiques (bugs corrigés)

### 1. Espaces dans les coordonnées symboliques
```latex
% CASSÉ : (54,  {Autres})   ← espace avant { → coord ' {Autres}' ≠ 'Autres'
% OK    : (54,{Autres})
```

### 2. Slash `/` dans les noms de coordonnées symboliques
```latex
% CASSÉ : symbolic y coords={Finance/Banque, Tech/IA}
%         \addplot coordinates {(120,{Finance/Banque})}
%         → pgfkeys interprète '/' comme séparateur de chemin
% OK    : symbolic y coords={Finance-Banque, Tech-IA}
%         \addplot coordinates {(120,{Finance-Banque})}
```

### 3. Noms de coordonnées modifiés dans ce rapport

| Original | Renommé (coord interne) |
|---|---|
| `Réact/Tech/FR/+5` | `React-FR` |
| `Python/IA/CH/+15` | `Python-CH` |
| `SAP/Ind./BE/+12` | `SAP-BE` |
| `COBOL/Fin./LU/+25` | `COBOL-LU` |
| `Transport/Retail` | `Transport-Retail` |
| `Industrie/RH` | `Industrie-RH` |
| `Tech/IA` | `Tech-IA` |
| `Finance/Banque` | `Finance-Banque` |
| `Secteur public` | `Secteur-public` |
| `BOAMP/FR` | `BOAMP-FR` |
| `TED/FR`, `TED/BE`, etc. | `TED-FR`, `TED-BE`, etc. |
| `LI-Jobs/FR`, etc. | `LI-Jobs-FR`, etc. |

---

## Règles hyperref / fancyhdr

```latex
% Dans Main.tex \hypersetup{...} :
plainpages=false,      % évite les duplicates page.1 (roman → arabic)
pdfpagelabels=true,    % labels PDF corrects

% Dans Main.tex avant \pagestyle{fancy} :
\setlength{\headheight}{14pt}   % fancyhdr exige ≥ 13.6pt
```

---

## Ordre de chargement des packages (important)

```
tabularx → array (auto)
...
\usepackage{titlesec}    ← AVANT minitoc
\usepackage{minitoc}     ← APRÈS titlesec (sinon conflit \chapter)
\dominitoc
...
\usepackage{hyperref}    ← toujours en dernier (ou quasi)
```

---

## Résultats du projet (données réelles au 2 mai 2026)

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

- NLP TF-IDF + LinearSVC : **75% accuracy** CV-5 (10 secteurs, 604 exemples)
- LLM Groq llama-3.1-8b-instant : messages en **1–3 secondes**
- Infrastructure : Docker Compose 5 services (api, postgres, redis, n8n, metabase)

---

## Bugs corrigés dans cette session (résumé)

1. `Chapter2.tex` — styles TikZ paramétrés avec `!` dans l'argument → styles explicites nommés
2. `Chapter3.tex` — `✗ ✅ ❌ ⏰ 🔗 🌐 ▶` → équivalents LaTeX
3. `Chapter3.tex` — `step/.style` → `pipstep/.style`
4. `Chapter3.tex` — coords pgfplots avec espaces et `/` → corrigés
5. `Chapter3.tex` — nœuds d'annotation WF03 sans `align=center` + `\\` → ajout `align=center`
6. `Chapter4.tex` — `step/.style` → `pipstep/.style`
7. `Chapter4.tex` — `\foreach` avec `/` dans valeurs → nœuds manuels
8. `Chapter4.tex` — `successbox[..., COBOL, France]` → titre sans virgules
9. `Chapter4.tex` — `✓` × 7 → `$\checkmark$`
10. `Chapter4.tex` — coords pgfplots avec espaces et `/` → corrigés
11. `Main.tex` — `\headheight` → 14pt
12. `Main.tex` — `plainpages=false, pdfpagelabels=true` dans hyperref
13. `Main.tex` — minitoc déplacé après titlesec
