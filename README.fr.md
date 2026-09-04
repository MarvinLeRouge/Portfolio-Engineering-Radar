# Portfolio Engineering Radar

> Suivi de la qualité d'ingénierie et amélioration continue, assistés par l'IA et fondés sur des preuves, pour un portfolio de projets logiciels.

**Portfolio Engineering Radar** est une plateforme locale de pilotage de la qualité d'ingénierie conçue pour évaluer, comparer, prioriser et améliorer continuellement un ensemble de projets logiciels.

Le projet est conçu pour un développeur web fullstack travaillant sur plusieurs repositories et plusieurs stacks technologiques. Son objectif n'est pas de remplacer le jugement d'ingénierie par une note générée par une IA, mais de combiner des analyses déterministes, une évaluation fondée sur des preuves, un référentiel de qualité versionné et un raisonnement assisté par IA au sein d'un système cohérent d'amélioration.

## Vision du projet

La gestion de plusieurs applications pose un problème difficile à résoudre repository par repository : les projets individuels peuvent progresser alors que le portfolio reste globalement hétérogène.

Portfolio Engineering Radar vise à mettre en place une boucle continue :

```text
Repositories
     ↓
Analyse automatisée
     ↓
Preuves
     ↓
Évaluation de la qualité
     ↓
Priorisation
     ↓
Roadmap
     ↓
Implémentation
     ↓
Ré-audit
     ↺
```

Le système doit permettre de répondre notamment aux questions suivantes :

- Quel est l'état actuel de chaque repository ?
- Quel est l'état global du portfolio ?
- Quels problèmes sont communs à plusieurs projets ?
- Que faut-il corriger en priorité ?
- Quel est l'impact attendu par rapport à l'effort nécessaire ?
- La roadmap représente-t-elle encore l'état réel du code ?
- La qualité d'ingénierie progresse-t-elle réellement dans le temps ?

## Principes fondamentaux

### Les preuves avant la notation

Les notes doivent être appuyées autant que possible par des éléments observables. Les outils déterministes doivent fournir les mesures et les findings ; l'IA doit principalement les interpréter, les mettre en relation, les prioriser et les expliquer.

### Une méthodologie de qualité versionnée

Les catégories, critères, règles, pondérations, système de notation et modèle de confiance doivent être explicitement définis et versionnés.

Une note obtenue aujourd'hui doit rester réellement comparable avec une note obtenue ultérieurement. Les évolutions de la méthodologie doivent donc être tracées et ne doivent jamais modifier silencieusement les mesures historiques.

### Une vision à l'échelle du portfolio

L'objectif n'est pas de rendre techniquement identiques tous les repositories.

Le système doit identifier les principes d'ingénierie qui peuvent être homogénéisés tout en préservant les différences légitimes entre stacks, architectures et domaines fonctionnels.

### Une roadmap vivante

La roadmap n'est pas un simple document de planification statique. Elle doit refléter l'état réel des repositories, être mise à jour après les audits et les travaux d'implémentation, et maintenir une traçabilité entre findings, améliorations et validations.

### Local-first

Les repositories étant disponibles localement, le système doit privilégier l'analyse locale et éviter de transmettre inutilement du code source ou des secrets à des services externes.

### Réévaluation continue

Une amélioration n'est pas considérée comme terminée simplement parce que du code a été modifié. Le système doit pouvoir réévaluer les critères concernés et fournir des preuves que l'amélioration attendue a effectivement été obtenue.

## Fonctionnalités prévues

- Analyse de plusieurs repositories
- Référentiel commun de qualité d'ingénierie
- Méthodologie de notation versionnée
- Findings fondés sur des preuves
- Intégration d'outils d'analyse statique et de sécurité
- Évaluation de l'architecture et de la maintenabilité
- Évaluation des tests et de la fiabilité
- Évaluation de la sécurité
- Évaluation de la CI/CD et de la developer experience
- Suivi de la dette technique
- Analyse transversale des projets
- Backlog d'améliorations priorisé
- Roadmap vivante
- Snapshots historiques de qualité
- Évolution des indicateurs du portfolio
- Dashboard local
- Analyse et planification assistées par IA
- Auto-évaluation de Portfolio Engineering Radar

## Environnement cible

Le système est initialement destiné à un développeur fullstack travaillant principalement avec des technologies telles que :

- Vue.js / Vue 3
- Python / FastAPI
- PHP / Laravel
- MongoDB et bases SQL
- Docker / Docker Compose
- Git / GitHub
- GitHub Actions

L'architecture doit rester consciente des spécificités des technologies utilisées sans rendre le modèle de qualité dépendant d'une stack particulière.

## Méthode de développement

Le projet sera développé par étapes explicites :

1. Définir l'architecture du système et la méthodologie de qualité.
2. Identifier et évaluer la toolchain d'analyse optimale.
3. Définir et versionner l'ensemble des catégories, critères, règles, pondérations et systèmes de notation.
4. Calibrer le framework sur un repository pilote.
5. Implémenter le moteur d'audit et le modèle de données.
6. Implémenter le dashboard local.
7. Auditer le portfolio.
8. Construire et maintenir la roadmap d'amélioration.
9. Ré-auditer régulièrement et mesurer les progrès réels.

La méthodologie doit être établie avant le premier audit complet du portfolio.

## État du projet

**Phase 4 : implémentation du système, en cours.**

Le modèle de données (`radar-core`) et le moteur d'orchestration/normalisation des outils (`radar-audit`) sont implémentés et en développement actif. `radar-audit` couvre actuellement les catégories 1 (Architecture & conception), 2 (Qualité du code) et 3 (Tests & fiabilité) du Quality Framework ; les catégories restantes, le dashboard local et la génération de rapports restent à faire. Voir `docs/roadmap.md` pour l'état détaillé et à jour.

## Documentation

- [Conception du système](docs/architecture/) — architecture par composant (`radar-core`, `radar-audit`)
- [Quality Framework](docs/quality-framework.md) — méthodologie versionnée : taxonomie, notation, modèle de confiance
- [Toolchain](docs/toolchain.md) — outils d'analyse évalués et sélectionnés par domaine
- [Roadmap](docs/roadmap.md) — avancement phase par phase
- [Architecture Decision Records](docs/adr/) — décisions enregistrées individuellement
- [Guide développeur](docs/guides/developer_guide.md) — installation locale, tests, pre-commit
- [Contexte produit](docs/product-context.md) — cadrage du problème et usage visé
- [Opérations](docs/operations.md) — faire tourner le système en local

## Langues

- [English README](README.md)
- [Documentation française](README.fr.md)

## Licence

[MIT](LICENSE)
