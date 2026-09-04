# Architecture de radar-core

> Version française | [English version](radar-core_architecture.md)

`radar-core` est le modèle de données partagé et la couche de migration
utilisés par tous les autres composants du système. Il ne contient
aucune logique d'orchestration propre : il définit les entités SQLModel,
les helpers de session de base de données, et l'historique des
migrations Alembic sur lesquels `radar-audit` (et plus tard l'API du
dashboard) lisent et écrivent.

## Responsabilités

- Définir le modèle de données d'audit sous forme de classes SQLModel (une table par classe)
- Posséder l'historique des migrations Alembic (`radar-core/alembic/`)
- Fournir les helpers `get_engine` / `get_session` (`radar_core.db`), incluant l'application des contraintes de clé étrangère sous SQLite puisque SQLite les désactive par défaut
- Fournir les enums partagés et le type de colonne `UTCDateTime` (`radar_core.enums`, `radar_core.types`) garantissant des timestamps conscients du fuseau horaire sur toutes les tables

`radar-core` ne communique jamais avec des outils externes ni avec le
système de fichiers d'un dépôt audité ; cette frontière appartient
entièrement à `radar-audit`.

## Carte des entités

```text
Repository
    └─ Audit (un par dépôt, par commit_sha)
           └─ ToolResult (un par exécution d'outil par sous-projet)

MethodologyVersion
    └─ Category
           └─ Criterion

ScoringRun (référence un Audit + une MethodologyVersion)
    └─ Score (par Criterion ou par Category)

Finding (référence un ScoringRun, un Criterion, optionnellement un ToolResult)
    └─ Evidence (référence le Finding, optionnellement un Score)
    └─ Recommendation (référence le Finding)

ImprovementTask
    └─ RoadmapItem (un-à-un, suit le statut/la preuve de complétion)
    └─ lié à Finding via FindingImprovementTaskLink (plusieurs-à-plusieurs)

Snapshot (état agrégé à un instant donné, table indépendante)
```

## Organisation des modules

```text
radar-core/src/radar_core/
    db.py            helpers engine/session, pragma FK SQLite
    enums.py         types enum partagés
    types.py         type de colonne UTCDateTime
    models/
        repository.py    Repository
        audit.py         Audit, ToolResult
        methodology.py   MethodologyVersion, Category, Criterion
        scoring.py       ScoringRun, Score
        finding.py       Finding, Evidence, Recommendation
        roadmap.py       ImprovementTask, RoadmapItem
        snapshot.py      Snapshot
        links.py         FindingImprovementTaskLink
```

## Décisions de conception clés

- **La sortie brute des outils est préservée.** `ToolResult.raw_output`
  stocke la sortie JSON complète de l'outil telle quelle ; la
  normalisation en `Finding`/`Score` se fait en aval dans `radar-audit`,
  de sorte qu'un constat puisse toujours être retracé jusqu'à la preuve
  exacte qui l'a produit.
- **Les audits sont clés sur `(repository_id, commit_sha)`.** Relancer un
  audit sur un commit inchangé réutilise la même ligne `Audit` plutôt que
  d'en créer une nouvelle.
- **La méthodologie est versionnée explicitement.** Chaque `ScoringRun`
  référence la `MethodologyVersion` par rapport à laquelle il a été
  scoré, afin que les poids ou définitions de critères puissent évoluer
  dans le temps sans invalider les scores historiques.
- **Les timestamps sont toujours conscients du fuseau horaire.** Le type
  `UTCDateTime` est utilisé sur chaque colonne datetime et est couvert
  par un test dédié vérifiant le round-trip UTC, pour éviter les bugs
  silencieux liés aux datetimes naïfs.

## Migrations

Alembic est configuré avec un `env.py` à URL explicite
(`radar-core/alembic/env.py`) : il exige `RADAR_DATABASE_URL` et ne
suppose jamais de chaîne de connexion par défaut, suivant la même règle
appliquée dans la CLI `radar-audit`. Voir le
[guide développeur](../guides/developer_guide.fr.md#base-de-données-et-migrations)
pour les commandes exactes.
