═══════════════════════════════════════════════════════════
  RAPPORT PFE — LeadGen Francophone 360+
  Template ESPRIT — LaTeX
  Auteur : Ferjani Malek — Mai 2026
═══════════════════════════════════════════════════════════

PRÉREQUIS
─────────
• TeX Live 2023+ (recommandé) ou MiKTeX
  Packages requis : geometry, babel, inputenc, fontenc, lmodern,
    microtype, setspace, graphicx, xcolor, tikz, pgfplots,
    fancyhdr, booktabs, tabularx, longtable, multirow, multicol,
    colortbl, array, amsmath, amssymb, listings, tcolorbox,
    minitoc, hyperref, varioref, float, caption, subcaption,
    pdfpages, eso-pic, enumitem, titlesec

COMPILATION (3 passes requises pour TOC + minitoc + hyperref)
─────────────────────────────────────────────────────────────
  pdflatex Main.tex
  bibtex Main
  pdflatex Main.tex
  pdflatex Main.tex

OU avec latexmk (automatique) :
  latexmk -pdf -f Main.tex

RÉSULTAT
────────
  Main.pdf  →  rapport complet

STRUCTURE DES FICHIERS
──────────────────────
  Main.tex          Fichier principal (preambule + include)
  garde_fin.tex     Page de couverture (TikZ)
  form.tex          Formulaire validation encadrants
  Dedicaces.tex     Dédicaces
  Remerciements.tex Remerciements
  Introduction.tex  Introduction générale
  Chapter1.tex      Chapitre 1 : Cadre du projet
  Chapter2.tex      Chapitre 2 : Analyse des besoins + Architecture
  Chapter3.tex      Chapitre 3 : Conception technique
  Chapter4.tex      Chapitre 4 : Réalisation et résultats
  Conclusion.tex    Conclusion générale
  garde_fin2.tex    4ème de couverture (Résumé / Abstract)
  bibliography.bib  Bibliographie BibTeX

CONTENU LATEX NOTABLES
──────────────────────
• Page de couverture entièrement en TikZ (bandes ESPRIT bleues/rouge)
• Diagrammes TikZ : architecture macro, flux collecteurs, pipeline,
  ERD, workflows n8n, NLP
• Graphiques pgfplots : score stacked bar, volumes collectés,
  comparaison NLP, distribution scores, score moyen par pays
• Boîtes tcolorbox : infobox, warningbox, successbox
• Listings Python3 + SQL avec coloration syntaxique
• minitoc (mini table des matières par chapitre)
• Bibliographie BibTeX (11 références)
═══════════════════════════════════════════════════════════
