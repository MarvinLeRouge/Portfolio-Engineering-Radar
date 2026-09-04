# radar-audit

> Version française | [English version](README.md)

Moteur d'orchestration d'outils et de normalisation pour [Portfolio-Engineering-Radar](../README.fr.md).

`radar-audit` détecte les sous-projets d'un dépôt, exécute les outils
d'analyse déterministes pertinents pour chaque stack détectée, et persiste
leurs résultats bruts au regard de la taxonomie versionnée du Quality
Framework. Voir [`docs/quality-framework.md`](../docs/quality-framework.md)
pour la méthodologie complète et [`docs/toolchain.md`](../docs/toolchain.md)
pour la sélection de chaque outil.

## Couverture

Actuellement câblés : 22 runners d'outils couvrant les catégories 1 à 3 du
Quality Framework.

| Catégorie | Critères couverts | Outils |
|---|---|---|
| 1. Architecture & conception | circularité des dépendances, présence de documentation de conception, taille des modules | dependency-cruiser, pydeps, radon, comptage statique de lignes |
| 2. Qualité du code | taux de réussite du lint, taux de réussite du type-check, complexité cyclomatique, pre-commit quality gate, duplication de code | Ruff, ESLint, Pint, mypy, tsc, PHPStan, Radon, PHPMD, jscpd |
| 3. Tests & fiabilité | taux de réussite des tests unitaires + couverture, tests d'intégration, tests E2E, exécution des tests en CI | pytest-cov, Vitest, Pest, inspection des workflows GitHub Actions, présence de Playwright |

Les catégories 4 à 15 ne sont pas encore implémentées ; voir
[`docs/roadmap.md`](../docs/roadmap.md).

## Prérequis

`radar-audit` écrit dans la même base SQLite que les migrations Alembic de
`radar-core`. Avant de lancer un premier audit réel (hors `--dry-run`),
appliquez les migrations sur la base cible :

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head

## Usage

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"
    uv run --package radar-audit radar-audit run <repo-name>
    uv run --package radar-audit radar-audit run --all
    uv run --package radar-audit radar-audit run <repo-name> --dry-run

`--dry-run` affiche les sous-projets détectés et les outils qui seraient
exécutés, sans toucher à la base de données.

Le périmètre des dépôts et la racine locale de checkout sont configurés
dans `portfolio.yaml` (versionné dans ce répertoire).
