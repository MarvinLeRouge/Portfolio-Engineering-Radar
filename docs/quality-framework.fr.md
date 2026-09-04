# Quality Framework v1.0

> Version française | [English version](quality-framework.md)

> Statut : **gelé, 2026-08-26.** Revu point par point (taxonomie, archétypes de scoring, poids, pénalités critiques, gestion N/A/données manquantes, critères par catégorie, lacunes d'outillage) directement avec le développeur, la même discipline de revue appliquée à `open-decisions.md` pour la Phase 0. C'est la méthodologie de référence pour la Phase 3 (calibration pilote) et au-delà, selon les règles de versioning du §6.
>
> S'appuie sur `docs/system-design.md` (modèle de données §5, système de confiance §8, stratégie de versioning §9, repris tels quels, non répétés ici) et `docs/toolchain.md` (outils validés + candidats, Phase 1/Phase 2). Remplace `system-design.md`§6-7 comme référence faisant autorité pour la taxonomie/le scoring.

---

## 1. Taxonomie finale

Les 15 catégories de `system-design.md`§6 sont conservées telles quelles (défaut D8 : pas de fusion/scission sans preuve issue du pilote).

```text
1. Architecture & conception          9. Observabilité / opérations
2. Qualité du code                   10. API / UX / qualité produit
3. Tests & fiabilité                 11. Gestion des dépendances
4. Sécurité                          12. Gestion de la configuration
5. Maintenabilité                    13. Qualité des données
6. Performance                       14. Expérience développeur
7. DevOps / CI-CD                    15. Dette technique
8. Documentation
```

Trois critères sont déjà gelés depuis la revue Phase 0 et **ne sont pas redéfinis ci-dessous** — voir `system-design.md`§6 pour leur définition complète, cités ici uniquement par référence :

- **D11** — catégorie 7, « Reverse proxy / parité environnement local-prod (Traefik) »
- **D12** — catégorie 2, « Gate de qualité pre-commit (hooks lint / format / type-check) »
- **D13** — catégorie 10, « Qualité de design graphique/visuel »

Signaux de périmètre différé, inchangés, toujours non résolus à ce stade (le défaut D8 s'applique, ce sont les données du pilote Phase 3 qui décident, pas une décision de bureau) :
- Catégorie 9 (Observabilité) — périmètre restreint pour un profil de développeur solo, voir §4.9 ci-dessous.
- Catégorie 10 (API/UX/qualité produit) — candidate à la scission (« qualité du contrat API » vs « UX/Visuel/qualité produit » plus étroite), toujours provisoire.
- Catégorie 13 (Qualité des données) — périmètre restreint pour un profil de développeur solo, voir §4.13 ci-dessous.

---

## 2. Archétypes de scoring des critères

Chaque critère ci-dessous est étiqueté avec l'un des trois archétypes, afin que le catalogue n'ait pas à redériver la mécanique de scoring pour chaque critère, seuls les critères d'archétype A ont besoin de conditions de niveau sur mesure.

| Archétype | Échelle | Quand l'utiliser | Précédent |
|---|---|---|---|
| **A — Ancré** | 0/2/4/6/8/10, chaque niveau lié à une condition explicite basée sur des preuves | Critères de type jugement ou à sévérité échelonnée | Règle de base `system-design.md`§7 |
| **B — Couverture** | `score = (couvert / applicable) × 10`, calculé, pas fixé à la main | Sortie d'outil en pourcentage/ratio (taux de réussite lint, taux de réussite type-check, couverture de tests, couverture de matrice) | Formule `IN_PROGRESS` de D12, généralisée |
| **C — Adoption** | 4 états `DONE`(10) / `IN_PROGRESS`(calculé ou 5) / `TODO`(0) / `N/A`(exclu) | Critères « cette pratique est-elle en place », pas un gradient de qualité | D11, D12 |

Les trois alimentent la même agrégation par moyenne pondérée (§3). Le `N/A` de l'archétype C et les propres conditions N/A des archétypes A/B utilisent tous la règle de gestion N/A identique (§3), pas de mécanisme séparé.

---

## 3. Modèle de scoring global

Finalise les points laissés ouverts dans `system-design.md`§7.

### 3.1 Poids

- **Poids des catégories :** délibérément non uniformes, décidés le 2026-08-26 (pas un ajustement dérivé du pilote Phase 3, un choix de priorité direct du développeur, le poids est intrinsèquement normatif, contrairement aux seuils de mesure qui ont besoin de preuves) :
  - **Sécurité : 10%**
  - **Tests & fiabilité : 10%**
  - **Les 13 autres catégories : 80/13 ≈ 6,15% chacune** (répartition égale du reste)
  - Total : 100%, par construction.
  - C'est toujours un défaut initial ouvert à révision, pas gelé pour toujours, en particulier le poids de la catégorie 10 (API/UX/qualité produit, portant actuellement le critère de design graphique à confiance MOYENNE/FAIBLE selon D13) est explicitement signalé pour une repondération future une fois qu'un critère fournissant des données véritablement quantifiables devient disponible (par exemple un signal outillé d'accessibilité/régression visuelle remplaçant ou complétant la couche interprétative actuelle). D'autres catégories pourront être revisitées de la même façon à mesure que les lacunes d'outillage se comblent (§5). Enregistré comme une montée de version MINEURE selon `system-design.md`§9, sauf si un ajustement futur dépasse la tolérance de montée MAJEURE de cette section.
- **Poids des critères au sein d'une catégorie :** égaux par défaut sauf mention explicite contraire dans une entrée du catalogue ci-dessous.

### 3.2 Pénalités critiques (liste concrète)

Revues et confirmées telles quelles, le 2026-08-26. Un ensemble défini et versionné de conditions plafonne le score d'une catégorie indépendamment de sa moyenne pondérée. Les quatre sont ancrées dans des outils déjà validés dans `docs/toolchain.md`, aucun nouvel outillage n'est supposé.

| # | Condition | Preuve | Catégorie plafonnée | Plafond |
|---|---|---|---|---|
| P1 | ≥1 secret confirmé trouvé dans l'historique Git suivi | Gitleaks (mode historique git, voir `toolchain.md`§Sécurité) | Sécurité | ≤ 2 |
| — | **Pré-filtre ajouté lors de la calibration pilote Phase 3 (GeoChallenge-Tracker, 2026-08-26) :** un hit brut Gitleaks `generic-api-key` dans un chemin `tests?/`/`test_*`, sur une variable nommée `fake_*`/`mock_*`/`dummy_*`, est un motif fort de fixture de test (6/6 hits sur ce pilote correspondaient, tous faux positifs sur des lignes comme `fake_token = "eyJ..."`) — un tel hit est maintenu à `PENDING_CONFIRMATION` (selon le gate de confirmation humaine, `system-design.md`§8) plutôt que compté comme « secret confirmé » pour P1 par défaut. Ceci restreint ce qui compte comme « confirmé » pour cette pénalité spécifique ; cela ne change pas les constats propres de Gitleaks ni les preuves brutes du critère 4.2. | — | — |
| — | **Pré-filtre élargi lors de la seconde calibration pilote (Summit-Stats, 2026-08-27) :** la même classe de faux positifs est réapparue, mais sur un motif de fichier différent, un hit `generic-api-key` sur `.env.prod.example` (un fichier gabarit committé, correspondant à une valeur d'apparence plausible comme `BCRYPT_ROUNDS=12`, pas un vrai secret). Ceci confirme que le motif n'est pas spécifique au nommage de tokens de test. Le pré-filtre couvre désormais aussi un hit dont le chemin de fichier correspond à `.env.*.example`/`.env.*.template`/`.env.*.sample`, maintenu à `PENDING_CONFIRMATION` sur la même base que le motif de fixture de test ci-dessus. | — | — |
| P2 | ≥1 CVE de sévérité CRITIQUE avec une version corrective connue disponible et non appliquée | Trivy (fs/image) / pip-audit / `pnpm audit` / `composer audit` | Sécurité | ≤ 4 |
| P3 | Un workflow CI existe et exécute la suite de tests, mais ce job échoue sur la branche par défaut (pas simplement absent) | actionlint + statut du job de test dérivé de la CI | Tests & fiabilité | ≤ 4 |
| P4 | Un gate de qualité pre-commit/CI est configuré (D12 `DONE`/`IN_PROGRESS`) mais des erreurs du type exact qu'il est censé bloquer sont présentes, mergées sur la branche par défaut | Constats Ruff / ESLint / PHPStan croisés avec les preuves D12 | Qualité du code | ≤ 5 |

Une catégorie plafonnée enregistre quand même sa valeur de moyenne pondérée non plafonnée à côté du plafond, afin que l'écart lui-même soit visible (pas juste le chiffre final), même principe que la génération de `Finding` par cellule de D12.

### 3.3 Gestion du N/A

Inchangé par rapport à `system-design.md`§7, rendu explicite aux deux niveaux : un critère (ou une catégorie entière, par exemple Performance pour un profil sans service runtime, voir §4.6) marqué `N/A` est exclu de la moyenne pondérée de son parent, son poids redistribué parmi les membres applicables restants, et la raison de l'exclusion enregistrée. Un dépôt n'est jamais pénalisé pour un critère ou une catégorie qui ne s'applique manifestement pas à lui.

### 3.4 Gestion des données manquantes

Inchangé par rapport à `system-design.md`§7 : un critère qui n'a pas pu être évalué (outil en échec, aucune preuve disponible) est enregistré comme absent, pas défaulté à 0 ni à N/A, et la confiance de la catégorie est dégradée en conséquence (la règle d'agrégation au minimum du §8 s'applique toujours).

### 3.5 Fraîcheur des preuves

Ajouté lors de la seconde calibration pilote Phase 3 (Summit-Stats, 2026-08-27). Un critère dont la preuve *pourrait* être lue depuis un artefact committé (un `coverage.xml`, `coverage-summary.json` committé, ou tout autre fichier de rapport généré que le dépôt cible suit) doit plutôt être évalué depuis une **exécution en direct effectuée par l'audit lui-même**, jamais en lisant directement cet artefact, même quand il est présent et que ses chiffres semblent plausibles. Cas confirmé : le `coverage.xml` committé de Summit-Stats montrait 73,97% de couverture d'instructions, apparemment en dessous du gate CI à 80% du dépôt lui-même ; un run `pest --coverage` frais a produit 91,4%, le fichier committé n'avait simplement pas été régénéré depuis un point antérieur de l'historique du dépôt. Un artefact périmé est indiscernable d'un artefact frais par simple inspection, ce n'est donc pas un jugement au cas par cas, c'est une règle permanente pour toute preuve générée par un outil pouvant devenir périmée entre deux commits (les rapports de couverture aujourd'hui, la même logique s'appliquerait par exemple à un SBOM committé ou un instantané d'audit de dépendances committé si l'un ou l'autre est un jour utilisé comme preuve). Voir la section Python de `toolchain.md` pour le détail au niveau de l'outil.

---

## 4. Catalogue des critères

Par catégorie : objectif, archétype, preuve/outil, note de poids, confiance de base, faux positifs / lacunes. Les critères déjà gelés (D11, D12, D13) sont cités, pas répétés.

### 4.1 Architecture & conception

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 1.1 | Direction / circularité des dépendances | A | dependency-cruiser (JS/TS), pydeps (Python), comptage de cycles. 0 cycle=10, 1-2=6, 3-5=4, >5=2 | HAUTE | FP : certains frameworks (ex. cross-refs du store Vuex) utilisent des motifs bidirectionnels intentionnels, maintenu au gate de confirmation (`system-design.md`§8) uniquement si cela pousserait le score vers sa bande supérieure |
| 1.2 | Documentation d'architecture présente | A | Présence de `DESIGN.md`/`ARCHITECTURE.md`/ADR et longueur non triviale | MOYENNE | Présence vérifiée, pas exactitude par rapport au code actuel |
| 1.3 | Distribution de la taille des modules | B | radon (proxy LOC/complexité Python) ; JS/PHP : aucun outil dédié validé pour l'instant, comptage LOC statique seulement | MOYENNE | Le LOC est un proxy faible de modularité ; outillage complet JS/PHP signalé comme lacune (§5) |
| 1.4 | Cohérence du style architectural | A | Couche de jugement LLM étroite, restreinte à « style unique dominant vs visiblement mixte », même discipline que le principe de tranche étroite de D13 | FAIBLE | Le gate de confirmation humaine s'applique dès que cela pousse vers la bande supérieure |

### 4.2 Qualité du code

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 2.1 | Taux de réussite propre du linter | B | Ruff / ESLint / PHPStan, constats vs fichiers scannés | HAUTE | S'exécute avec la propre config du dépôt, voir note `toolchain.md` sur ESLint |
| 2.2 | Réussite du type-checking | B | mypy / `tsc --noEmit` / PHPStan | HAUTE | |
| 2.3 | Complexité cyclomatique | A | radon (Python, validé). JS : règle ESLint `complexity`, config détenue par l'audit (candidat). PHP : ruleset PHPMD `codesize` (candidat) | HAUTE (Python) / MOYENNE-en-attente-de-smoke-test (candidats JS, PHP identifiés le 2026-08-26, pas encore validés) | Candidats ajoutés à `toolchain.md`, toujours une lacune jusqu'au smoke-test (§5) |
| 2.4 | Gate de qualité pre-commit | C | Voir D11/D12, référencé de façon croisée, pas redéfini | — | |
| 2.5 | Duplication de code | A | jscpd (candidat, outil unique couvrant Python/JS-TS/PHP/Vue, MIT à confirmer, activement développé) | — | Lacune jusqu'au smoke-test (§5). Rejeté : PMD-CPD (nécessite un runtime JVM, aucun avantage sur jscpd ici) |

### 4.3 Tests & fiabilité

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 3.1 | Tests unitaires présents & passants, avec couverture | B | pytest+coverage / Vitest / Pest, taux de réussite et % de couverture | HAUTE | |
| 3.2 | Tests d'intégration | A | Heuristique : fichiers de test sous un chemin nommé intégration, ou important les couches DB/HTTP | MOYENNE | Dépendant de la convention de nommage ; un dépôt avec une convention différente pourrait être sous-détecté |
| 3.3 | Tests E2E | C | Playwright présent & câblé dans la CI = `DONE` ; présent mais pas en CI = `IN_PROGRESS` ; absent = `TODO` pour les dépôts orientés web, `N/A` pour les dépôts sans UI | MOYENNE | Présence/câblage seulement, l'exécution n'est pas vérifiée dans le smoke test Phase 1 (`toolchain.md`) |
| 3.4 | La CI exécute la suite de tests | C | Dérivé d'actionlint : une étape de workflow invoque pytest/Vitest/Pest | HAUTE | |
| 3.5 | Qualité / pertinence des tests | A | Couche de jugement LLM étroite (assertions significatives vs tautologiques) | FAIBLE | Le gate de confirmation humaine s'applique à la bande supérieure |

### 4.4 Sécurité

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 4.1 | Vulnérabilités de dépendances (CVE) | A | pip-audit / `pnpm audit` / `composer audit`, échelonné par sévérité | HAUTE | Alimente P2 (§3.2) |
| 4.2 | Secrets dans l'historique suivi | A | Gitleaks, mode historique git | HAUTE | Alimente P1 (§3.2) |
| 4.3 | Constats SAST | A | Semgrep, échelonné par sévérité | HAUTE | Taux de FP suivi par règle via la boucle de feedback `human_verdict` de D14 |
| 4.4 | Vulnérabilités d'image conteneur | A | Scan d'image Trivy, comptage HIGH/CRITICAL | HAUTE | `N/A` si aucune image construite localement (précondition `toolchain.md`) |
| 4.5 | Durcissement du Dockerfile | B | Densité de constats Hadolint | HAUTE | |
| 4.6a | Hygiène AuthN/AuthZ | A | Semgrep, rulesets registry authN/authZ (`p/security-audit` + packs spécifiques au framework), candidat, non smoke-testé | — | Couverture probablement inégale entre les stacks FastAPI/Laravel/Vue-Node, à vérifier au smoke-test ; toujours une lacune jusqu'à validation (§5) |
| 4.6b | En-têtes de sécurité HTTP | A | mdn-http-observatory (candidat, vérification runtime contre un serveur actif, score noté) ; candidat de repli `shcheck` (présence uniquement) | — | Même précondition « nécessite un serveur actif » que Lighthouse/Playwright ; toujours une lacune jusqu'à validation (§5) |

### 4.5 Maintenabilité

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 5.1 | Points chauds de complexité | A | Partage la preuve avec 2.3, cadrage distinct : signale les fichiers atypiques plutôt que la moyenne à l'échelle du dépôt | HAUTE (Python) / MOYENNE-en-attente-de-smoke-test (candidats JS, PHP) | Référence croisée à 2.3, pas pondéré deux fois séparément |
| 5.2 | Code mort / exports inutilisés | A | knip (JS, validé). Python : vulture (candidat, MIT, activement maintenu). PHP : ruleset PHPMD `unusedcode` (candidat) | HAUTE (JS) / MOYENNE-en-attente-de-smoke-test (candidats Python, PHP identifiés le 2026-08-26, pas encore validés) | vulture rapporte une confiance par constat (60-100%) qui vaut la peine d'être remontée telle quelle ; toujours une lacune jusqu'au smoke-test (§5) |
| 5.3 | Documentation dans le code (couverture docstring/commentaire) | B | Python : `docvet` (candidat, MIT, 2026) préféré à `interrogate` (plus ancien, maintenance disputée par un outil concurrent). PHP : `php-censor/phpdoc-checker` (candidat, BSD-2-Clause). JS/TS : aucun candidat trouvé, les outils de « couverture » existants y mesurent la couverture de type TS, pas la présence de commentaires | — | Python/PHP : lacune jusqu'au smoke-test (§5). JS/TS : véritable lacune ouverte, aucun outil identifié |

### 4.6 Performance — **partiellement résolue, backend/BDD explicitement hors périmètre**

Revu le 2026-08-26 : la performance frontend et la performance backend/BDD ne sont pas le même type de problème et sont traitées différemment, pas regroupées dans une seule catégorie différée.

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 6.1 | Performance frontend | A | Lighthouse, échelonné par score (90-100→10, 70-89→6-8, 50-69→4, <50→2/0) | MOYENNE | `N/A` pour les dépôts sans UI (même population que D13). Outil candidat, **pas encore smoke-testé**, ajouté à `docs/toolchain.md` comme candidat en attente d'une validation façon Phase 1, même statut que Playwright déjà (nécessite un serveur actif, une étape de build, un navigateur headless). Des doutes qui méritent d'être portés, pas glissés sous le tapis : (a) **reproductibilité**, les scores Lighthouse sont connus pour varier d'une exécution à l'autre selon la charge machine/les conditions réseau, ce qui va à l'encontre du principe de stabilité des scores déjà appliqué ailleurs (D7) ; ceci nécessite une mitigation explicite (par exemple moyenner N exécutions, ou un environnement fixe à ressources contraintes) avant que le critère puisse être fiable à confiance HAUTE ; (b) **exhaustivité**, le score de performance de Lighthouse couvre uniquement les métriques de chargement de page (LCP, TBT, CLS, etc.), pas la logique métier ni la performance d'interaction, donc un score élevé est un signal étroit, limité au temps de chargement, pas « ce frontend performe bien » au sens plein. |

**Performance backend / BDD : aucun critère défini en v1.0, pas `N/A`.** Discuté et décidé le 2026-08-26 : contrairement aux autres lacunes du §5 (où un outil manque simplement mais le critère lui-même est bien défini), la performance backend/BDD n'a pas de *définition* établie pour commencer, il n'existe pas de seuil absolu objectif (« assez rapide ») sans un SLA par projet, et aucun dépôt du périmètre n'en définit un. Le seul mécanisme plausible est un **détecteur de dérive/régression auto-référentiel** (stocker une référence min/max/médiane par dépôt au moment de l'audit, comparer les audits ultérieurs à celle-ci) plutôt qu'un score de qualité absolu 0-10, ceci réutilise l'entité `Snapshot` existante (`system-design.md`§5, déjà prévue pour « l'état au moment de l'audit, pour comparaison de tendance ») mais est architecturalement différent de tous les autres critères de ce framework :

- Il ne peut produire aucun signal lors du premier audit d'un dépôt (pas encore de référence à laquelle comparer).
- Il mesure la *stabilité relative à l'historique propre du dépôt*, pas la qualité absolue, un dépôt qui a toujours été lent apparaîtrait comme « stable », jamais comme « mauvais ».
- Il nécessite un protocole de benchmark reproductible (quelle requête, quelles conditions) qu'aucun outil validé dans `docs/toolchain.md` ne fournit actuellement.

Compte tenu de ces trois limitations structurelles, la performance backend/BDD est **exclue entièrement du Quality Framework v1.0, délibérément, pas différée comme une lacune d'outillage**. La revisiter ne vaut la peine que si/quand le développeur définit des cibles de performance concrètes par projet, à ce moment-là le mécanisme basé sur la dérive ci-dessus est un point de départ plausible, documenté ici comme une idée, pas construit.

### 4.7 DevOps / CI-CD

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 7.1 | Présence & santé de la CI | A | Workflow GH Actions présent + actionlint propre | HAUTE | |
| 7.2 | Reverse proxy / parité local-prod | C | Voir D11, référencé de façon croisée, pas redéfini | — | |
| 7.3 | Durcissement de la construction de conteneur | A | Partage la preuve avec 4.4/4.5, cadrage DevOps (« le pipeline est-il propre ») vs cadrage Sécurité (« l'image est-elle vulnérable ») | HAUTE | Référence croisée, pas pondéré deux fois |
| 7.4 | Automatisation du déploiement | C | Présence de `build-push.yml`/`build-deploy.yml`, câblé à une étape de push vers un registre | MOYENNE | Présence seulement, aucune vérification runtime des déploiements réels (l'accès API GitHub de D6 pourrait plus tard vérifier l'historique d'exécution) |

### 4.8 Documentation

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 8.1 | Exhaustivité du README | A | Heuristique : présence des en-têtes de section standards (installation, usage, aperçu d'architecture) | MOYENNE | |
| 8.2 | Documentation d'architecture | A | Partage la preuve avec 1.2, cadrage Documentation (« présente et lisible ») vs cadrage Architecture (« reflète la structure réelle ») | MOYENNE | Référence croisée, pas pondéré deux fois |
| 8.3 | Documentation d'API | C | Schéma OpenAPI/Swagger présent & servi (auto-docs FastAPI, Laravel L5-Swagger) ; `N/A` pour les dépôts sans API | MOYENNE | |

### 4.9 Observabilité / opérations — périmètre restreint (selon le signal D8/§1)

Délibérément cadré pour un profil de développeur solo, pas une stack d'observabilité d'entreprise.

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 9.1 | Logging structuré | A | Heuristique : bibliothèque/formatter de logging structuré vs `print`/`console.log` nu | MOYENNE | Heuristique basée sur grep, aucun outil dédié validé |
| 9.2 | Intégration de suivi d'erreurs | C | SDK Sentry (ou équivalent) présent & configuré, exemple réel déjà observé sur Triton (`sentry-sdk` dans ses dépendances) lors du smoke test Phase 1 | MOYENNE | Présence ≠ correctement câblé (par exemple un DSN factice) |
| 9.3 | Endpoint de health-check | C | Route `/health`/`/healthz` présente ; `N/A` pour les dépôts sans service longue durée (même logique N/A que D11) | MOYENNE | |

### 4.10 API / UX / qualité produit — provisoire (candidate à la scission selon D8)

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 10.1 | Qualité de design graphique/visuel | A | Voir D13, référencé de façon croisée, pas redéfini | — | |
| 10.2 | Cohérence du contrat API | A | Spectral, ruleset intégré `spectral:oas` (candidat, Apache 2.0, activement maintenu) | — | Nécessite un fichier de spec OpenAPI exporté (précondition plus légère qu'un serveur actif, même classe que pytest, voir `toolchain.md`) ; lacune jusqu'au smoke-test (§5) |
| 10.3 | Accessibilité (WCAG) | — | Déjà partie de la couche factuelle de D13 | — | Pas un critère séparé, évite le double comptage |

### 4.11 Gestion des dépendances

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 11.1 | Fraîcheur des dépendances | B | `pip list --outdated` / `npm`&`pnpm outdated` / `composer outdated` (D15, `toolchain.md`) | HAUTE | Conditionné par l'opt-in d'accès registre de D15 ; `N/A` quand l'accès n'est pas accordé pour un run (jamais scoré silencieusement), et `N/A` pour les dépôts non pinnés sans fichier de lock selon le constat JobFlow dans `toolchain.md` |
| 11.2 | Conformité des licences | A | Python : `pip-licenses` (candidat, MIT, activement maintenu). JS : `license-checker-evergreen` (fork maintenu, candidat). PHP : `composer licenses --format=json` (natif, outil déjà validé, aucun nouveau risque) | — | Contrairement à 11.1, aucun appel réseau nécessaire (lit les métadonnées de paquets déjà installés/verrouillés), pas conditionné par D15. Python/JS : lacune jusqu'au smoke-test (§5) ; PHP : effectivement prêt, réutilise une commande déjà validée |
| 11.3 | Empreinte des dépendances | A | Comptage brut de dépendances relatif à la taille du dépôt | FAIBLE | Aucune référence établie pour l'instant, nécessite des données de calibration Phase 3 sur le portfolio lui-même avant que ce critère soit fiable |

### 4.12 Gestion de la configuration

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 12.1 | Secrets jamais codés en dur | — | Partage la preuve avec 4.2, cadrage Gestion de la configuration (« la config est-elle externalisée ») vs cadrage Sécurité (« un secret a-t-il déjà fuité ») | HAUTE | Référence croisée, pas pondéré deux fois |
| 12.2 | Séparation des environnements | A | Heuristique : `.env.example`/`.env.testing`/`.env.prod.example` distincts ou équivalent, exemple réel observé sur Summit-Stats lors de la Phase 1 | MOYENNE | |
| 12.3 | Validation de la config au démarrage | C | Heuristique : Pydantic Settings (Python) / motif de validation de config Laravel présent | MOYENNE | Aucun outil dédié validé, heuristique de motif de code |

### 4.13 Qualité des données — périmètre restreint (selon le signal D8/§1)

Délibérément cadré pour un profil de développeur solo, pas des critères de gouvernance de données d'entreprise.

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 13.1 | Versioning du schéma/des migrations | C | Répertoire de migrations avec fichiers séquentiels horodatés (Laravel, Alembic, Django) | HAUTE | Structurel, déterministe |
| 13.2 | Validation des entrées aux frontières | A | Heuristique : modèles Pydantic sur les routes FastAPI / classes `FormRequest` Laravel | MOYENNE | Aucun outil dédié validé (candidat : règles Semgrep personnalisées, pas encore construites) |
| 13.3 | Qualité des données/fixtures de test | C | Motif Faker/factory présent pour les tests vs littéraux codés en dur, exemple réel observé sur Summit-Stats (`fakerphp/faker`, répertoire factories) | MOYENNE | |

### 4.14 Expérience développeur

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 14.1 | Documentation d'onboarding | A | Présence de `CONTRIBUTING.md` / script d'installation, exemple réel sur Summit-Stats (script `"setup"` de `composer.json` chaînant install+migrate+build) | MOYENNE | |
| 14.2 | Reproductibilité du dev local | A | Partage la preuve avec 7.2 (D11) plus la présence d'un profil dev Docker Compose | MOYENNE | Référence croisée, pas pondéré deux fois |
| 14.3 | Standardisation des scripts/tâches | A | Scripts `package.json`/`composer.json` ou `Makefile` couvrant le cycle de vie courant (dev, test, lint, build) | HAUTE | Vérification de présence structurelle |

### 4.15 Dette technique

| # | Critère | Archétype | Preuve / outil | Confiance | Notes |
|---|---|---|---|---|---|
| 15.1 | Densité de TODO/FIXME | A | Comptage basé sur grep, normalisé par KLOC | HAUTE (comptage brut) / FAIBLE (classification de sévérité) | La densité elle-même est déterministe ; classifier un TODO donné comme dette réelle vs note légitime à venir nécessite une couche interprétative étroite, gardée séparée du signal brut à confiance HAUTE |
| 15.2 | Code mort/inatteignable | A | Partage la preuve avec 5.2 | HAUTE (JS) / MOYENNE-en-attente-de-smoke-test (candidats Python, PHP) | Référence croisée, pas pondéré deux fois |
| 15.3 | Actualité de la version framework/runtime | A | Version de moteur pinnée vs réellement en cours d'exécution, exemple réel déjà observé lors de la Phase 1 (`npm warn EBADENGINE` sur HexaRot/Summit-Stats, une discordance `engines` vs runtime installé remontée en effet de bord d'autres exécutions d'outils) | HAUTE | |

---

## 5. Lacunes ouvertes reportées (explicites, pas silencieuses)

Un dépôt ne doit jamais être pénalisé pour une lacune qui est la faute du système d'audit, pas la sienne. Les critères sans outil validé sont scorés `N/A` (pas 0, pas silencieusement ignorés) jusqu'à ce qu'une future passe d'outillage comble la lacune :

- **2.3 / 5.1 / 15.2** — détection de complexité cyclomatique et de code mort pour JS et PHP, plus code mort pour Python. Candidats identifiés le 2026-08-26 (règle ESLint `complexity` en config détenue par l'audit pour la complexité JS, PHPMD `codesize`/`unusedcode` pour la complexité+code mort PHP, vulture pour le code mort Python, tous ajoutés à `toolchain.md`), mais aucun smoke-testé pour l'instant, donc toujours compté comme une lacune jusqu'à validation.
- **2.5** — détection de duplication de code. Candidat identifié le 2026-08-26 : jscpd (outil unique, Python/JS-TS/PHP/Vue), ajouté à `toolchain.md`, pas smoke-testé.
- **4.6a / 4.6b** — hygiène authN/authZ et en-têtes de sécurité HTTP. Candidats identifiés le 2026-08-26 (rulesets registry Semgrep pour 4.6a, mdn-http-observatory pour 4.6b, `shcheck` comme repli plus léger), ajoutés à `toolchain.md`, mais aucun smoke-testé pour l'instant.
- **5.3** — couverture docstring/commentaire. Python (`docvet`, candidat) et PHP (`php-censor/phpdoc-checker`, candidat) identifiés le 2026-08-26, ajoutés à `toolchain.md`, pas smoke-testés. JS/TS n'a aucun candidat du tout, les outils de « couverture » existants y mesurent la couverture de type TS, une métrique différente, pas un substitut.
- **10.2** — linting de contrat API (OpenAPI). Candidat identifié le 2026-08-26 : Spectral (ruleset `spectral:oas`), ajouté à `toolchain.md`, pas smoke-testé.
- **11.2** — conformité des licences. Candidats identifiés le 2026-08-26 : `pip-licenses` (Python), `license-checker-evergreen` (JS), `composer licenses --format=json` (PHP, natif, déjà validé), ajoutés à `toolchain.md`. Python/JS pas smoke-testés ; PHP effectivement prêt (aucun nouvel outil impliqué).
- **6.1 (Performance frontend)** — Lighthouse est candidat, pas encore smoke-testé (nécessite une validation façon Phase 1 : installation éphémère, licence, exécution contre un dépôt du périmètre) ; porte aussi des doutes ouverts de reproductibilité/exhaustivité, voir §4.6.

**La performance backend/BDD n'est pas dans cette liste** — revue le 2026-08-26 et délibérément exclue de la v1.0 plutôt que traitée comme une lacune d'outillage, voir §4.6 pour la raison (aucune définition objective n'existe sans un SLA par projet qui n'est défini nulle part dans ce portfolio).

Ces lacunes, plus la liste des pénalités critiques (§3.2) et le schéma de pondération égale par défaut (§3.1), sont les parties de ce framework les plus susceptibles de bouger en premier une fois les données du pilote Phase 3 disponibles.

---

## 6. Versioning

Identifiant : **Quality Framework v1.0**, gelé le 2026-08-26, selon le format et les règles de montée de version de `system-design.md`§9. C'est le premier enregistrement `MethodologyVersion`. Tout changement après ce point (rééquilibrage de poids, comblement de lacune une fois un outil candidat smoke-testé, fusion/scission de taxonomie) est une montée de version selon ces règles, pas une édition silencieuse de ce document.
