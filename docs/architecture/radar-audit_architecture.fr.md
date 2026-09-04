# Architecture de radar-audit

> Version française | [English version](radar-audit_architecture.md)

`radar-audit` orchestre l'exécution d'outils sur un dépôt et normalise
les résultats bruts dans le modèle de données `radar-core`. Il s'invoque
comme une commande CLI ponctuelle (`radar-audit run ...`), pas comme un
service tournant en continu, et ne modifie jamais le dépôt audité.

## Pipeline

```text
portfolio.yaml
    ↓
PortfolioConfig (config.py)
    ↓
resolve_repository / get_or_create_audit (orchestrator.py)
    ↓
discover_subprojects (discovery.py)         compute_exclude_paths (worktree.py)
    ↓                                              ↓
plan_audit → AuditPlan (sous-projets × exclude_paths)
    ↓
planned_runs (AuditPlan × DEFAULT_RUNNERS, filtré par stack/scope)
    ↓
execute_audit : chaque ToolRunner.run() invoqué avec isolation des crashs
    ↓
lignes ToolResult (raw_output préservé tel quel)
    ↓
normalizers/*.py : raw_output → Finding / Score, par critère du Quality Framework
```

## Responsabilités

- **`config.py`** : charge et valide `portfolio.yaml` (`repos_root` + liste de dépôts) ; lève `PortfolioConfigError` plutôt que d'échouer silencieusement sur une config malformée.
- **`discovery.py`** : détecte les sous-projets dans un dépôt via fichier manifeste (`pyproject.toml`/`requirements.txt` -> python, `package.json` -> javascript, `composer.json` -> php), sur un niveau de profondeur plus la racine du dépôt elle-même ; retombe sur un unique sous-projet de stack `unknown` si aucun manifeste n'est trouvé.
- **`worktree.py`** : calcule la liste des chemins à exclure de l'analyse, dérivée de `git worktree list`, afin que les worktrees imbriqués ne soient jamais comptés deux fois par des outils comme la couverture ou la détection de duplication.
- **`orchestrator.py`** : résout les lignes `Repository`/`Audit` (clées sur `commit_sha`, réutilisées lors d'une relance sur un commit inchangé), construit l'`AuditPlan`, filtre les runners par `stack`/`scope`, et exécute chaque run avec une isolation des crashs par outil afin qu'un outil en échec n'interrompe jamais l'audit complet.
- **`runner.py`** : définit le protocole `ToolRunner` (`tool_name`, `tool_version`, `supported_stacks`, `scope`, `timeout_s`, `run()`) implémenté par chaque intégration d'outil, ainsi que la dataclass `RawToolOutput` retournée par chaque `run()`.
- **`runners/`** : une implémentation `ToolRunner` par outil externe (dependency-cruiser, pydeps, ruff, mypy, ESLint, TypeScript, PHPStan, Pint, radon, phpmd, jscpd, pytest, Vitest, Pest, pre-commit, présence de workflow CI, présence Playwright, et présence de documentation de conception).
- **`normalizers/`** : une fonction par critère, transformant un `ToolResult.raw_output` (ou un ensemble de ceux-ci) en `Finding`/`Score` pour un critère spécifique du Quality Framework.
- **`taxonomy/seed.py`** : seed de façon idempotente la taxonomie Quality Framework v1.0 (lignes `MethodologyVersion`/`Category`/`Criterion`) depuis une source de vérité YAML, afin que la taxonomie en base corresponde toujours au document de méthodologie gelé.
- **`cli.py`** : le point d'entrée Typer (`radar-audit run <repo>|--all [--dry-run] [--config path]`), reliant le pipeline ci-dessus à une session `radar-core` et enregistrant les `DEFAULT_RUNNERS`.

## Décisions de conception clés

- **Isolation des crashs par outil.** Un runner qui plante ou dépasse son timeout produit un `ToolResult` en échec plutôt que d'interrompre l'audit ; tous les autres runners s'exécutent quand même.
- **Le filtrage stack/scope se fait au moment de la planification.** `planned_runs()` croise la stack détectée de chaque sous-projet avec les `supported_stacks` de chaque runner, et son `scope` (`repo` vs `subproject`) avec la structure du sous-projet, afin que les outils spécifiques à un langage ne s'exécutent jamais sur la mauvaise stack.
- **Les worktrees sont exclus globalement**, pas par runner : `compute_exclude_paths` s'exécute une fois par audit et son résultat est propagé à chaque invocation d'outil acceptant une liste d'exclusion, plusieurs runners initiaux ayant indépendamment compté deux fois des fichiers de worktrees imbriqués avant cette centralisation.
- **`--dry-run` ne touche jamais la base de données ni n'invoque aucun outil externe** ; il affiche uniquement le plan résolu, ce qui le rend sûr pour déboguer `portfolio.yaml` ou la détection de stack.
- **Ne suppose jamais d'emplacement de base de données.** `RADAR_DATABASE_URL` doit être défini explicitement pour toute invocation autre que dry-run ; voir [`docs/operations.md`](../operations.fr.md#secrets) pour la justification.

## Ajouter un nouvel incrément de normalisation

Voir la section
["Ajouter un nouveau tool runner"](../guides/developer_guide.fr.md#ajouter-un-nouveau-tool-runner)
du guide développeur pour les étapes concrètes.
