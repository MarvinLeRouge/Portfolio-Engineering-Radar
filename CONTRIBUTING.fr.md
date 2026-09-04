Version française | [English version](CONTRIBUTING.md)

---

# Contribuer à Portfolio Engineering Radar

Il s'agit principalement d'un projet personnel. Les contributions externes (signalements de bugs, corrections, petites améliorations) sont bienvenues mais dans un périmètre limité.

## Prérequis

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) pour la gestion des dépendances

## Installation locale

```bash
git clone https://github.com/MarvinLeRouge/Portfolio-Engineering-Radar.git
cd Portfolio-Engineering-Radar
uv sync
uv run pre-commit install
```

## Lancer les tests

```bash
uv run --package radar-core pytest
uv run --package radar-audit pytest
```

## Workflow

1. Forker le dépôt et créer une branche à partir de `main`.
2. Faire la modification, avec des tests qui la couvrent.
3. Commiter en suivant la convention ci-dessous.
4. Pousser et ouvrir une pull request vers `main`.
5. Les hooks pre-commit (voir ci-dessous) doivent passer avant la revue.

## Nommage des branches

| Type | Préfixe |
|---|---|
| Fonctionnalité | `feat/description-courte` |
| Correction | `fix/description-courte` |
| Maintenance | `chore/description-courte` |
| Documentation | `docs/description-courte` |
| Refactoring | `refactor/description-courte` |
| Tests | `test/description-courte` |

Minuscules, kebab-case, sans caractères spéciaux.

## Convention de commit

Suivre [Conventional Commits](https://www.conventionalcommits.org/), impératif, minuscules, sans point final, avec une section `Modified files:` obligatoire :

```
<type>(<scope optionnel>): <résumé court>

Modified files:
- chemin/vers/fichier-a.ext - ce qui a été modifié
- chemin/vers/fichier-b.ext - ce qui a été modifié
```

Types : `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`, `ci`.

## Style de code

`ruff` (lint + format) et `mypy --strict` tournent sur `radar-core` et `radar-audit` via des hooks pre-commit (`.pre-commit-config.yaml`). Il n'y a pas encore de pipeline CI qui les impose à distance (voir [`docs/roadmap.md`](docs/roadmap.fr.md)) — lancez `uv run pre-commit run --all-files` localement avant d'ouvrir une pull request.

## Code de conduite

Ce projet suit un [Code de conduite](CODE_OF_CONDUCT.fr.md). En participant, vous vous engagez à le respecter.

## Licence

En contribuant, vous acceptez que vos contributions soient distribuées sous la licence du projet (voir [LICENSE](LICENSE)).
