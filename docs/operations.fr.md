# Opérations

> Version française | [English version](operations.md)

Référence opérationnelle minimale. C'est un système local, mono-utilisateur,
offline-first : il n'y a pas encore de déploiement hébergé.

## Lancer le moteur d'audit

`radar-audit` s'invoque manuellement via une commande CLI ; ce n'est pas
un service tournant en continu. Voir le
[guide développeur](guides/developer_guide.fr.md) pour l'installation et
l'usage.

## Données

Toutes les données d'audit structurées vivent dans la base de données
pointée par `RADAR_DATABASE_URL`. En usage local, il s'agit généralement
d'un fichier SQLite gitignored ; rien dans le schéma ne suppose SQLite
spécifiquement (géré via les migrations Alembic dans `radar-core`).

Les sorties brutes des outils capturées pendant une exécution sont
conservées à côté des résultats normalisés plutôt que jetées, afin qu'un
constat puisse toujours être retracé jusqu'à l'invocation d'outil qui l'a
produit.

Il n'y a pas encore d'automatisation de sauvegarde : sauvegarder
manuellement le fichier de base de données si son contenu compte pour
vous (par exemple avant d'exécuter une migration destructrice).

## CI / automatisation

- `CHANGELOG.md` est régénéré automatiquement à chaque push sur `main` via [`.github/workflows/changelog.yml`](../.github/workflows/changelog.yml) (ouvre une pull request, ne pousse jamais directement sur `main`)
- Il n'y a pas encore de pipeline CI exécutant les tests ou les gates `ruff`/`mypy` à distance ; ils s'exécutent localement via des hooks pre-commit (voir [`CONTRIBUTING.md`](../CONTRIBUTING.fr.md)). Suivi dans [`docs/roadmap.md`](roadmap.fr.md)

## Secrets

Le moteur d'audit lit les dépôts locaux en lecture seule et ne nécessite
aucun identifiant ni clé d'API pour son périmètre actuel. Si un futur
critère nécessite un accès réseau ou une clé d'API, celui-ci devra être
opt-in et explicitement signalé (voir la décision sur l'accès réseau dans
[`docs/adr/`](adr/)).
