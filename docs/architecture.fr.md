🇫🇷 Version française | [🇬🇧 English version](architecture.md)

---

# Architecture - Portfolio Engineering Radar

> Référence technique publique. Voir [architecture radar-core](architecture/radar-core_architecture.fr.md) et [architecture radar-audit](architecture/radar-audit_architecture.fr.md) pour les détails d'implémentation.

## Vue d'ensemble

Portfolio Engineering Radar audite un portefeuille de dépôts locaux selon un Quality Framework versionné, en stockant les résultats dans un modèle de données partagé :

- **`radar-core`** - modèle de données SQLModel partagé et historique de migrations Alembic. Aucune logique d'orchestration propre ; tous les autres composants lisent et écrivent dedans.
- **`radar-audit`** - CLI mono-exécution (`radar-audit run ...`) qui détecte les sous-projets, exécute des outils externes épinglés par stack détectée avec isolation des crashs, et normalise la sortie brute des outils en lignes `Finding`/`Score` selon la taxonomie figée.
- **`radar-api` / `radar-dashboard`** (prévu) - API FastAPI lecture/écriture et SPA Vue 3 la consommant, pas encore implémenté.

## Structure du projet

```
portfolio-engineering-radar/
├── radar-core/
│   └── src/radar_core/
│       ├── db.py         # helpers engine/session
│       ├── enums.py       # types enum partagés
│       ├── types.py       # type de colonne UTCDateTime
│       └── models/        # Repository, Audit, Finding, Score, Roadmap, ...
├── radar-audit/
│   └── src/radar_audit/
│       ├── config.py       # chargement/validation de portfolio.yaml
│       ├── discovery.py     # détection de sous-projets par fichier manifeste
│       ├── worktree.py       # calcul des chemins à exclure
│       ├── orchestrator.py    # résolution Repository/Audit, exécution de l'AuditPlan
│       ├── runner.py           # protocole ToolRunner
│       ├── runners/             # un ToolRunner par outil externe
│       ├── normalizers/          # raw_output -> Finding/Score, par critère
│       └── taxonomy/seed.py       # seed de la taxonomie Quality Framework
└── docs/
    ├── architecture/    # architecture radar-core/radar-audit
    ├── adr/             # architecture decision records
    └── guides/          # guide développeur
```

## Pour aller plus loin

- [Architecture radar-core](architecture/radar-core_architecture.fr.md)
- [Architecture radar-audit](architecture/radar-audit_architecture.fr.md)
- [Quality Framework](quality-framework.fr.md)
- [Toolchain](toolchain.fr.md)
- [Registre des décisions d'architecture](adr/README.md)
- [Guide développeur](guides/developer_guide.fr.md)
- [Contexte produit](product-context.fr.md)
- [Opérations](operations.fr.md)
