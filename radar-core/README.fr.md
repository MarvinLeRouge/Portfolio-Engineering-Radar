# radar-core

> Version française | [English version](README.md)

Modèle de données partagé (SQLModel) et migrations Alembic pour [Portfolio-Engineering-Radar](../README.fr.md).

`radar-core` définit la couche de persistance partagée par tous les autres
packages : `Repository`, `Audit`, `MethodologyVersion`, `Category`,
`Criterion`, `ToolResult`, `Finding`, `Evidence`, `Score`,
`Recommendation`, `ImprovementTask`, `RoadmapItem` et `Snapshot`. Voir
[`docs/quality-framework.md`](../docs/quality-framework.md) pour la
méthodologie encodée par ces tables, et
[`docs/architecture/radar-core_architecture.md`](../docs/architecture/radar-core_architecture.md)
pour la conception du schéma.

## Prérequis

La base de données est SQLite par défaut, adressée via `RADAR_DATABASE_URL`.

    export RADAR_DATABASE_URL="sqlite:///$(pwd)/radar.db"

## Appliquer les migrations

    uv run --package radar-core alembic -c radar-core/alembic.ini upgrade head

## Créer une nouvelle migration

    uv run --package radar-core alembic -c radar-core/alembic.ini revision --autogenerate -m "<description courte>"

Relisez la migration générée avant de la committer : l'autogénération
d'Alembic ne capture pas toujours correctement toutes les contraintes ou
tous les index.

## Lancer les tests

    uv run --package radar-core pytest
