# Audit pilote Phase 3 — GeoChallenge-Tracker

> Version française | [English version](pilot-audit-geochallenge-tracker.md)

> Run manuel, 2026-08-26. Le système d'orchestration/tableau de bord n'existe pas encore (c'est la Phase 4) — ceci est une passe manuelle des outils **validés** de `docs/toolchain.md` contre GeoChallenge-Tracker, notée à la main selon les archétypes et le modèle de `docs/quality-framework.md`, pour calibrer le framework avant son implémentation. Les outils candidats signalés « non smoke-testés » dans `toolchain.md` n'ont délibérément **pas** été exécutés ici — ils restent des lacunes indépendamment des résultats du pilote, selon `quality-framework.md`§5. Les sorties brutes des outils vivent dans le scratchpad de session, non committées (éphémères, reproductibles à la demande) ; ce document est l'enregistrement durable.

---

## 1. Ce qui a été exécuté

| Domaine | Outils | Résultat |
|---|---|---|
| Sécurité | Semgrep, Gitleaks, Trivy (fs), pip-audit | 2 WARNING Semgrep, 6 constats Gitleaks (tous faux positifs, voir §3), 3 CVE Trivy + 4 mauvaises configurations, 1 CVE pip-audit (déjà suppressé en CI avec une justification documentée) |
| Python | Ruff, mypy, radon, pytest+coverage | Ruff propre, mypy propre (après correctif, voir §3), radon : 618 blocs (2×F, 13×D), 1291/1291 tests unitaires réussis |
| JS/TS | ESLint, tsc, knip, Vitest | ESLint 42 erreurs (100% faux positifs, voir §3), tsc propre, knip 39 constats de code mort (2 faux positifs, voir §3), 419/419 tests Vitest réussis |
| Architecture | dependency-cruiser, pydeps | 0 violation circulaire/orpheline (frontend), graphe backend résolu proprement (126 modules) |
| Conteneurs | Hadolint, Trivy (image) | 3 constats Hadolint (Dockerfile backend), 201 CVE sur l'image backend (188 HIGH/13 CRITICAL), 60 CVE sur l'image frontend (56 HIGH/4 CRITICAL) |
| Git/CI | actionlint | 2 constats (shellcheck, variable non guillemetée dans `build-push.yml`) |
| Heuristiques structurelles | Preuves D11/D12, README/DESIGN.md, OpenAPI, engines, densité de TODO | voir §2 |

---

## 2. Notation catégorie par catégorie

Seules les catégories/critères avec des preuves directement recueillies pendant cette passe sont notés. Les critères dont le seul outil candidat est « non smoke-testé » (selon `toolchain.md`) restent `N/A`/lacune, inchangés par ce pilote. Les critères de jugement LLM 1.4 et 3.5 ont été évalués dans une passe de lecture de code de suivi (aucun nouvel outillage, voir ci-dessous) ; 10.1 a encore besoin d'une passe UI rendue (navigateur) non effectuée dans ce run CLI uniquement — laissé non noté, signalé en §4.

### 1. Architecture & conception
- 1.1 Direction/circularité des dépendances — **10** (0 cycle, dependency-cruiser et pydeps propres tous les deux)
- 1.2 Documentation architecturale — **10** (`DESIGN.md`, 1897 mots, substantiel)
- 1.3 Distribution de la taille des modules — non noté (lacune d'outillage JS/PHP, selon `toolchain.md` ; le côté Python a des données radon mais aucun seuil de distribution de taille dédié encore défini)
- 1.4 Cohérence du style architectural — **4** (visiblement mélangé, pas un style dominant unique : 5/15 fichiers de routes backend suivent un motif propre de contrôleur-fin/délégation-de-service avec `response_model` typé — `auth.py`, `meta.py`, `my_challenge_progress.py`, `my_challenge_tasks.py`, `zones.py` ; les routes du domaine central construisent plutôt des requêtes MongoDB directement dans le gestionnaire de route et retournent des dicts non typés — `caches.py` (6/6 routes, 0 `response_model`), `caches_elevation.py`, `caches_geocoding.py`, `referentials.py` ; plusieurs fichiers mélangent les deux motifs dans le même fichier — `my_challenges.py`, `my_challenge_targets.py`, `my_profile.py`. Le frontend montre le même clivage : les composables (`useXData`) sont utilisés dans la plupart des pages, mais plusieurs de ces mêmes pages appellent aussi `api.get()` directement pour des données auxiliaires au lieu de passer par un composable — ex. `Calendar.vue`, `Details.vue`, `Matrix.vue`, `Tasks.vue`.)

### 2. Qualité du code
- 2.1 Taux de passage linter propre — **10** (Ruff propre ; les 42 erreurs d'ESLint sont 100% des faux positifs, voir §3 — le taux de passage réel sur la source effective est propre)
- 2.2 Passage du type-checking — **10** (mypy propre, tsc propre)
- 2.3 Complexité cyclomatique — **6** (Python : 502 A / 72 B / 29 C / 13 D / 2 F blocs sur 618 — la grande majorité est correcte, mais 2 fonctions au rang F, complexité 70 et 62, sont de vrais points chauds ; JS/PHP reste une lacune d'outillage)
- 2.4 Gate qualité pre-commit — **10** (D12 : matrice complète 6/6 couverte — ruff lint+format+mypy backend, prettier+eslint+vue-tsc frontend, confirmé en lisant `.pre-commit-config.yaml` directement)
- 2.5 Duplication de code — non noté (candidat jscpd, non smoke-testé)

### 3. Tests & fiabilité
- 3.1 Tests unitaires présents et réussis, avec couverture — **10** (1291/1291 backend, 419/419 frontend, les deux au vert ; % de couverture non extrait cette passe mais les deux suites sont substantielles et au vert)
- 3.4 La CI exécute la suite de tests — **10** (`ci.yml` : les jobs `backend-test` et `frontend-unit` exécutent tous deux les vraies suites avec upload de couverture)
- 3.3 Tests E2E — **5 (EN COURS)** (Playwright configuré, script `test:e2e` présent, mais non câblé dans `ci.yml` — correspond exactement à la note de smoke-test de la Phase 1)
- 3.5 Qualité/pertinence des tests — **9** (échantillonnage de `test_dto_validation.py`, `test_calendar_verification.py` (backend) et `calendar-data.spec.ts` (frontend) : les assertions vérifient des valeurs calculées précises et de vrais cas limites — comptages de jours d'année bissextile, dédoublonnage de jours dupliqués, calcul de taux de complétion, réactivité — pas des vérifications de vérité tautologiques. Un grep sur toute la suite a trouvé 0 motif `assert True`/résultat-nu côté backend et seulement 4/598 expectations faibles `toBeTruthy()`/`not.toThrow()` côté frontend sur un total de 1861 assertions backend et 598 frontend — les assertions significatives dominent. Mise en garde : 4 fichiers backend — `_test_progress.py`, `_test_targets_smoke.py`, `_test_user_challenge_tasks_suite.py`, `_test_user_challenge_tasks_verbose.py`, 1228 lignes au total — sont nommés avec un underscore en tête, donc pytest ne les collecte jamais ; code de test orphelin, renvoi croisé 15.2, n'affecte pas la qualité de la suite active mais est une dette de code mort méritant d'être signalée séparément)

### 4. Sécurité
- 4.1 Vulnérabilités de dépendances — **6** (pip-audit : 1 CVE, déjà triée et suppressée en CI avec une justification documentée et re-vérifiée — `PYSEC-2026-1325`/attaque temporelle Minerva d'ecdsa, non exploitable puisque le dépôt ne signe les JWT qu'avec HS256 ; `npm audit` (non exécuté dans la première passe) : 2 HIGH, les deux avec un correctif disponible — dépendance transitive `flowbite-vue` et `nanoid`, le correctif nécessite un bump de version majeure pas encore appliqué)
- 4.2 Secrets dans l'historique suivi — **10** (0 vrai secret ; les 6 constats bruts de Gitleaks sont le motif de faux positif du §3, aucun ne devant déclencher P1)
- 4.4 Vulnérabilités des images de conteneurs — **2 (non plafonné : voir ci-dessous)** (image backend, Debian 13.6 : 13 CRITICAL, 0 avec un correctif encore publié — dette réelle mais non actionnable, ne déclenche pas P2 ; image frontend, Alpine 3.23.3 + Node : **4 CRITICAL avec un correctif disponible et non appliqué** — `libcrypto3`, `libssl3`, `tar`, `esbuild`/stdlib — c'est le déclencheur P2 concret)
- 4.5 Durcissement du Dockerfile — **6** (3 avertissements Hadolint : `apt-get`/`pip` non pinnés, `--no-cache-dir` manquant ; plus une mauvaise config Trivy : les deux Dockerfiles s'exécutent en root, aucun `HEALTHCHECK`)

**Vérification de pénalité critique (§3.2) :** P1 ne se déclenche **pas** (0 vrai secret, voir §3). **P2 se déclenche** : la vérification croisée de suivi Trivy/disponibilité-de-correctif (signalée comme ouverte dans la première passe) a trouvé 4 CVE CRITICAL sur l'image frontend avec un correctif publié non appliqué (reconstruire contre une base Alpine + Node/esbuild patchée les éliminerait). Selon `quality-framework.md`§3.2, le score de catégorie est plafonné à **4** (moyenne non plafonnée des 4 critères notés ci-dessus : 6,0). C'est une vraie confirmation que le mécanisme P2 fonctionne comme prévu, pas une clause théorique.

### 7. DevOps / CI-CD
- 7.1 Présence & santé de la CI — **10** (`ci.yml` à 5 jobs, tous les chemins au vert ; actionlint propre à part 2 notes shellcheck mineures)
- 7.2 Proxy inverse / parité local-prod — **10** (D11 : labels Traefik présents et correctement différenciés dans `docker-compose.yml` (dev, HTTP simple) et `docker-compose.prod.yml` (TLS + Let's Encrypt) — cas d'école FAIT)
- 7.4 Automatisation du déploiement — **10** (`build-push.yml` : construit et pousse les deux images vers GHCR au merge)

### 8. Documentation
- 8.1 Complétude du README — **10** (installation/setup, aperçu architectural, fonctionnalités, captures d'écran — tout est présent)
- 8.3 Documentation API — **10** (FastAPI instancié sans surcharge de `docs_url` → auto-docs Swagger/OpenAPI par défaut actifs)

### 9. Observabilité / opérations
- 9.1 Logging structuré — **6** (`logging.getLogger(__name__)` utilisé de façon cohérente à travers les services — vrai logger, pas de `print` nu, mais aucun formateur structuré/JSON confirmé)
- 9.2 Intégration de suivi d'erreurs — **0 (À FAIRE)** (aucun Sentry ou équivalent trouvé ni dans `backend/requirements.txt` ni dans `frontend/package.json`)
- 9.3 Endpoint de health-check — **10** (route `/health` présente, modèle de réponse `HealthCheck`)

### 11. Gestion des dépendances
- 11.1 Fraîcheur des dépendances — `N/A` cette passe (opt-in de vérification registre D15 non exercé)
- 11.3 Empreinte des dépendances — non noté (pas encore de référence de portfolio, selon la propre note du critère)

### 12. Gestion de configuration
- 12.2 Séparation des environnements — **10** (`.env`, `.env.example`, `.env.test` tous présents et distincts)
- 12.3 Validation de config au démarrage — **10** (`Settings(BaseSettings)` via `pydantic-settings`, confirmé dans `backend/app/core/settings.py`)

### 13. Qualité des données
- 13.1 Versionnage de schéma/migration — **0 (À FAIRE)** (aucun répertoire de migrations ni mécanisme de version de schéma trouvé — une vraie lacune pour une app MongoDB sans outil de migration au niveau ODM, pas un angle mort d'outillage)
- 13.3 Qualité des données/fixtures de test — **0 (À FAIRE)** (aucun motif faker/factory trouvé dans `backend/tests` ; contrairement à Summit-Stats, les tests semblent utiliser des littéraux en ligne)

### 14. Expérience développeur
- 14.1 Documentation d'onboarding — **10** (`CONTRIBUTING.md` présent, la section installation du README est détaillée)
- 14.3 Standardisation des scripts/tâches — **10** (les scripts `package.json` couvrent dev/test/lint/build/typecheck ; le backend a un cycle de vie équivalent via `requirements-dev.txt` + commandes documentées)

### 15. Dette technique
- 15.1 Densité TODO/FIXME — **~23 occurrences** à travers `backend/app` + `frontend/src` (compte brut seulement, aucune normalisation KLOC faite cette passe, aucune classification de sévérité — la couche interprétative n'a pas été exécutée)
- 15.3 Fraîcheur des versions framework/runtime — **10** (`engines.node` pinné à un intervalle réel, `>=20 <=24`)

---

## 3. Constats de calibration — faux positifs et corrections d'invocation d'outils

C'est la vraie valeur de la Phase 3 : les endroits où le framework figé ou la chaîne d'outils validée ont besoin d'une correction *avant* que la Phase 4 ne construise de l'automatisation autour.

### 3.1 Gitleaks : 6/6 constats sont des faux positifs sur de faux tokens de test

Les 6 occurrences sont des correspondances `generic-api-key` sur des lignes comme `fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def"` dans `backend/tests/test_auth.py` et `backend/tests/integration/test_endpoints_auth.py` — des fixtures de test clairement nommées, pas de vrais secrets. C'est exactement le scénario pour lequel D14 (boucle de retour `human_verdict`) a été conçue, mais cela suggère aussi un **pré-filtre bon marché** qui mérite d'être ajouté à la logique de pénalité critique P1 elle-même : une correspondance `generic-api-key` à l'intérieur d'un chemin de fichier correspondant à `tests?/` ou `test_*`, sur une variable nommée `fake_*`/`mock_*`/`dummy_*`, est un motif assez fort pour rester en `PENDING_CONFIRMATION` par défaut plutôt que de faire confiance au compte brut de Gitleaks pour le plafond P1. Recommandé comme correction Phase 3 à la condition P1 de `quality-framework.md`§3.2 — pas une refonte du framework, un raffinement de la notion de secret « confirmé ».

### 3.2 ESLint : un `eslint .` naïf à la racine du dépôt ramasse du bruit vendorisé/généré

Exécuter `npx eslint .` depuis la racine du dépôt (plutôt que le périmètre du propre `npm run lint` du dépôt) a ramassé `backend/.venv/lib/.../coverage_html.js` et `backend/htmlcov/coverage_html_cb_*.js` — des fichiers JS tiers/générés qui se trouvent exister localement (gitignored, jamais committés) mais ne font pas partie de l'arbre source réel. Les 42 « erreurs » sont toutes du bruit provenant de ces deux fichiers ; la vraie source frontend est propre. **Cause racine :** le propre `eslint.config.js` du dépôt n'ignore que `frontend/dist`/`frontend/coverage`/`node_modules` parce que son propre script de lint ne scanne jamais en dehors de `frontend/` ; l'outil d'audit a cassé cette hypothèse en scannant `.` à la racine du dépôt. C'est la même classe de piège déjà documentée pour la découverte de Dockerfile (`toolchain.md`§Conteneurs) et le mode filesystem de Gitleaks (`toolchain.md`§Sécurité). **Correction nécessaire :** l'invocation d'ESLint doit réutiliser le périmètre de lint propre et configuré du dépôt (lire la cible du script `lint` de `package.json`) plutôt que de recourir par défaut à `.`, ou au minimum exclure `.venv/`, `htmlcov/`, `__pycache__/` en plus de `node_modules/`.

### 3.3 mypy a besoin des dépendances runtime de la cible installées, contredisant le cadrage « analyse statique pure » de `toolchain.md`

`uvx mypy --ignore-missing-imports app` a échoué franchement (`Error importing plugin "pydantic.mypy": No module named 'pydantic'`) parce que le `pyproject.toml` de ce dépôt déclare le plugin `pydantic.mypy`. mypy a dû être exécuté comme `uvx --with-requirements requirements.txt --with mypy mypy ...` à la place — le même motif d'installation éphémère déjà utilisé pour pytest, pas le motif « juste la source de la cible » que la section JS/TS de `toolchain.md` sous-entend pour ses outils purement statiques. **Correction nécessaire :** mettre à jour la section Python de `toolchain.md` pour noter que mypy a besoin des propres dépendances runtime de la cible installées chaque fois que le dépôt configure un plugin de type-checking (Pydantic, Django, SQLAlchemy, etc.) — pas universellement, mais de façon détectable (présence de `[tool.mypy] plugins = [...]` dans `pyproject.toml`/`mypy.ini`).

### 3.4 knip signale de vrais points d'entrée comme fichiers morts sans config `entry`

`frontend/src/App.vue` et `frontend/src/main.ts` — les vrais points d'entrée de l'app Vue — ont été signalés sous `files` (inutilisés) parce que l'invocation par défaut `npx knip` n'a déclaré aucun point d'entrée via `knip.json`/`package.json#knip`. C'est le mode de faux positif bien connu de knip pour les projets non configurés. **Correction nécessaire :** soit rédiger un `knip.json` minimal détenu par l'audit (déclarant `entry: ["frontend/src/main.ts"]`, `project: ["frontend/src/**"]`) réutilisé à travers tous les dépôts basés sur Vite du portfolio, soit traiter `App.vue`/`main.ts`/`index.ts` comme un motif de point d'entrée toujours exclu avant de compter le type de constat `files` de knip dans le score 5.2.

### 3.5 le stdout de knip est pollué par les effets de bord de la propre config de la cible

`npx knip --reporter json` a affiché la sortie `console.log` de chargement dotenv de `playwright.config.ts` *avant* le payload JSON, parce que knip évalue les fichiers de config (y compris `playwright.config.ts`, référencé depuis `vitest.config.ts`) pendant la découverte. Le stdout brut n'était pas du JSON valide avant de localiser le préfixe `{"issues"` et de découper à partir de là. **Correction nécessaire :** toute orchestration future autour de knip ne doit pas supposer un stdout propre — localiser le payload JSON de façon défensive (premier `{` qui parse) plutôt que `json.loads(stdout)` directement. Mérite une note d'une ligne dans la section JS/TS de `toolchain.md`.

---

## 4. Éléments ouverts non résolus par cette passe

- **10.1 (design graphique, D13)** — toujours pas évalué. Sa couche factuelle (contraste WCAG, points de rupture responsive) a besoin de l'UI réellement rendue — une passe navigateur, pas juste de l'outillage CLI. 1.4 et 3.5 ont été résolus dans une passe de lecture de code de suivi (aucun rendu nécessaire, voir §2) et ne bloquent plus la validation de la Phase 3 ; 10.1 est la seule lacune interprétative restante.
- **Vérification croisée de pénalité critique 4.1/4.4 (P2)** — résolue cette passe : les scans d'image Trivy (backend + frontend) et `npm audit` ont été croisés avec la disponibilité de correctifs. Résultat : P2 se déclenche sur l'image frontend (4 CRITICAL avec un correctif disponible), la catégorie Sécurité est plafonnée à 4. Voir §2.
- **Catégorie 6 (Performance)** — correctement hors périmètre pour cette passe : Lighthouse est un candidat non validé (reste une lacune indépendamment des résultats du pilote), la performance backend/BDD est délibérément exclue de la v1.0 (`quality-framework.md`§4.6).
- **11.1 (fraîcheur des dépendances)** — correctement `N/A` : l'opt-in de vérification registre D15 n'a pas été exercé pour ce run, ce n'est pas un problème de framework.

---

## 5. Corrections de framework recommandées (pour `quality-framework.md`)

1. **Condition P1 §3.2** — ajouter le pré-filtre de fixture de test décrit au §3.1 ci-dessus, afin qu'un motif évident de faux token dans un fichier de test ne déclenche pas aveuglément une suspicion `PENDING_CONFIRMATION` au même poids qu'un vrai identifiant committé.
2. **Entrée mypy de `toolchain.md`** — documenter la mise en garde de détection de plugin du §3.3 (dépendances runtime nécessaires quand un plugin mypy est configuré).
3. **Entrée ESLint de `toolchain.md`** — documenter la mise en garde de périmètre du §3.2 (réutiliser le périmètre de chemin du propre script de lint du dépôt, ne pas recourir par défaut à `.`).
4. **Entrée knip de `toolchain.md`** — documenter le besoin de config de point d'entrée (§3.4) et la mise en garde de parsing du stdout (§3.5).

Aucune de ces corrections n'est un changement de taxonomie, de poids, ou de modèle de notation — la structure du framework a bien tenu face à un dépôt réel et assez mature. Les quatre corrections sont toutes des corrections de précision d'invocation de la chaîne d'outils, exactement le genre de constat que la Phase 3 est censée faire remonter avant que la Phase 4 ne durcisse ces invocations en orchestration automatisée.
