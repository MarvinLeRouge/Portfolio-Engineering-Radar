🇫🇷 Version française | [🇬🇧 English version](roadmap.md)

---

# Feuille de route

Miroir publié et versionné de la feuille de route de développement du
projet. Le tracker de travail non versionné (mis à jour plus fréquemment
pendant le développement actif) se trouve dans
`docs/work-in-progress/TODO.md`.

Suit l'avancement phase par phase. Les cases sont mises à jour au fur et
à mesure de l'avancement de chaque phase.

## Phase 0 — Architecture du système d'audit

- [x] Inspecter l'environnement local disponible
- [x] Identifier les dépôts potentiellement concernés (lecture seule, aucune modification de contenu)
- [x] Identifier les stacks utilisées
- [x] Analyser les contraintes du projet
- [x] Proposer l'architecture globale du système
- [x] Proposer la structure de données
- [x] Proposer la taxonomie initiale
- [x] Proposer le système de scoring
- [x] Proposer le système de confiance
- [x] Proposer la stratégie de versioning de la méthodologie
- [x] Proposer la stratégie de roadmap
- [x] Proposer l'architecture du dashboard
- [x] Proposer la liste des outils candidats
- [x] Identifier les points nécessitant une décision humaine
- [x] Produire `docs/system-design.md`
- [x] Produire les fiches de décision d'architecture (`docs/adr/`)
- [x] Revue humaine des décisions ouvertes, bloquante pour la Phase 1 jusqu'à résolution

## Phase 1 — Découverte et sélection de la chaîne d'outils

- [x] Évaluer les outils candidats par langage/domaine (sécurité, Python, JS/TS, PHP, architecture/dépendances, conteneurs, Git/CI)
- [x] Valider la disponibilité locale et la licence des outils retenus
- [x] Documenter la chaîne d'outils finale et les alternatives rejetées (`docs/toolchain.md`)

## Phase 2 — Définition finale des catégories, règles, critères, scoring

- [x] Finaliser la taxonomie (catégories + ajustements justifiés)
- [x] Définir des critères mesurables par catégorie (objectif, preuve, outils, niveaux, poids, dépendances, confiance, faux positifs)
- [x] Définir le modèle de scoring hiérarchique (critère -> catégorie -> global)
- [x] Définir les pénalités critiques, la gestion du N/A, la gestion des données manquantes
- [x] Geler le **Quality Framework v1.0** (`docs/quality-framework.md`)

## Phase 3 — Calibration sur un dépôt pilote

- [x] Sélectionner le dépôt pilote (voir `docs/pilot-audit-geochallenge-tracker.fr.md`)
- [x] Réaliser un audit complet dessus (passe manuelle)
- [x] Revoir la pertinence des critères, faux positifs/négatifs, poids, effort
- [x] Réaliser un second audit pilote sur un dépôt structurellement différent (Laravel/PHP + Vue/JS, voir `docs/pilot-audit-summit-stats.fr.md`) pour vérifier la cohérence inter-dépôts
- [x] Corriger le framework en fonction des constats
- [x] Confirmer le Quality Framework v1.0 comme référence pour le premier audit global

## Phase 4 — Implémentation du système

- [x] Implémenter le modèle de données (Repository, Audit, MethodologyVersion, Category, Criterion, Finding, Score, Evidence, Recommendation, ImprovementTask, RoadmapItem, Snapshot, ToolResult)
- [ ] Implémenter l'orchestration des outils et la normalisation des résultats bruts
  - [x] Moteur d'orchestration central (`radar-audit`) : configuration de portfolio, découverte des sous-projets, exclusion des worktrees, protocole `ToolRunner` avec isolation des crashs, seeding de la taxonomie Quality Framework v1.0, résolution Repository/Audit, CLI Typer
  - [ ] Normalisation des résultats bruts par catégorie du Quality Framework (un incrément par catégorie)
    - [x] Catégorie 1 — Architecture & conception : dependency-cruiser + pydeps, présence DESIGN.md/ARCHITECTURE.md/ADR, taille des modules via radon + comptage statique de lignes
    - [x] Catégorie 2 — Qualité du code : taux de réussite du lint, taux de réussite du type-check, complexité cyclomatique, gate pre-commit, duplication de code
    - [x] Catégorie 3 — Tests & fiabilité : taux de réussite des tests unitaires, tests d'intégration, exécution des tests en CI, présence de tests E2E
    - [ ] Catégories 4 à 15 (Sécurité, Maintenabilité, Performance, DevOps/CI-CD, Documentation, Observabilité/opérations, API/UX/qualité produit, Gestion des dépendances, Gestion de la configuration, Qualité des données, Expérience développeur, Dette technique)
- [ ] Implémenter le dashboard local (backend + frontend)
- [ ] Implémenter la génération de rapports (global + par dépôt)

## Phase 5 — Audit complet du portfolio

- [ ] Exécuter l'audit sur tous les dépôts identifiés
- [ ] Générer les documents globaux (`executive-summary`, `portfolio-scorecard`, `cross-project-analysis`, etc.)
- [ ] Générer les documents par dépôt

## Phase 6 — Construction du backlog et de la roadmap

- [ ] Convertir les constats en tâches d'amélioration priorisées
- [ ] Calculer les indicateurs de ROI (impact/effort/réduction de risque, clairement marqués comme des estimations)
- [ ] Publier la roadmap vivante

## Phase 7 — Suivi continu et réaudits

- [ ] Réauditer après les travaux d'implémentation
- [ ] Détecter les constats résolus/nouveaux/régressés avec preuves
- [ ] Détecter les divergences entre roadmap et code
- [ ] Suivre les métriques internes du système (stabilité des scores, taux de faux positifs, reproductibilité)
