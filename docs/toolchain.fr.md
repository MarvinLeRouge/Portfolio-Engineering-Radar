# Chaîne d'outils — Phase 1

> Version française | [English version](toolchain.md)

> Statut : en cours. Chaque domaine est smoke-testé (installation éphémère, exécution rapide contre un dépôt du périmètre, vérification de licence) et validé avant de passer au suivant, selon le prompt maître §9-10.
> Stratégie d'installation : éphémère uniquement (`uvx`, `npx`/`pnpm dlx`, sous-commandes natives `npm`/`pnpm`/`composer`, ou Docker pour les binaires Go seuls sans wrapper de gestionnaire de paquets), voir [`docs/adr/0004-toolchain-installation-strategy.md`](adr/0004-toolchain-installation-strategy.md).
> **Règle de sécurité npx (trouvée le 2026-08-26, voir Architecture/dépendances ci-dessous) :** npm laisse un paquet publier un binaire CLI sous n'importe quel nom, indépendamment du nom du paquet, `npx <bin-name>` se résout par *nom de binaire*, ce qui est un vecteur de confusion de dépendances si un paquet sans rapport (ou malveillant) revendique ce même nom de binaire dans le registre. Toujours invoquer sous la forme `npx --package=<nom-exact-du-paquet-npm> -- <bin-name>`, jamais `npx <bin-name>` nu, pour chaque outil npx éphémère de ce document, y compris ceux déjà validés ci-dessus avant que cette règle ne soit trouvée (`tsc`, dont le paquet est `typescript`, pas `tsc`).

---

## Sécurité

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| Semgrep | `uvx semgrep` — fonctionne directement, sortie JSON propre | LGPL 2.1 | **Conservé** |
| Gitleaks | Aucun wrapper `npx`/`uvx` (binaire Go) — via Docker `zricethezav/gitleaks` | MIT | **Conservé**, avec une décision de config requise (ci-dessous) |
| Trivy (scan filesystem) | Aucun wrapper `npx`/`uvx` — via Docker `aquasec/trivy` | Apache 2.0 | **Conservé** |
| pip-audit | `uvx pip-audit -r requirements.txt` échoue : les builds Python gérés par uv sont livrés sans `ensurepip`, donc la création de venv éphémère interne de l'outil plante. Contournement : `uvx --python /usr/bin/python3.13 pip-audit ...` (force le Python système, qui a `ensurepip`) | Apache 2.0 | **Conservé**, avec le contournement `--python` documenté comme config requise |
| `pnpm audit` | Natif (pnpm déjà présent), fonctionne directement, JSON | fait partie de pnpm | **Conservé** |
| `composer audit` | Natif (composer déjà présent), fonctionne directement, JSON | fait partie de Composer | **Conservé** |
| Semgrep, ruleset authN/authZ (lacune catégorie 4.6a) | Pas encore évalué — même binaire `uvx semgrep` déjà validé ci-dessus, avec des rulesets registry ciblant les mauvaises configurations d'auth (`p/security-audit` et packs spécifiques au framework) | LGPL 2.1 | **Conservé comme candidat**, non smoke-testé. Couverture probablement inégale entre les frameworks réels du portfolio (FastAPI, Laravel, Vue/Node), à vérifier par stack au smoke-test |
| mdn-http-observatory (lacune catégorie 4.6b) | Pas encore évalué — installable via npm, `mdn-http-observatory-scan <url>` contre un serveur actif, produit un score noté (CSP, HSTS, X-Frame-Options, cookies, CORS, etc.), traduisible sur l'échelle ancrée 0/2/4/6/8/10 | MPL-2.0 (à confirmer au smoke-test) | **Conservé comme candidat**, non smoke-testé. Nécessite un serveur actif, même classe de précondition que Lighthouse/Playwright. Candidat de repli : `shcheck` (MIT, `santoru/shcheck`), plus léger mais moins faisant autorité (vérification de présence seulement, pas de méthodologie notée) |

**Décision de config (validée le 2026-08-26) :** Gitleaks doit scanner **l'historique Git suivi** (mode par défaut), jamais le scan filesystem brut `--no-git`. Smoke-testé sur JobFlow : un scan filesystem brut a signalé de vrais fichiers d'identifiants (`token.json`, `credentials.json`, etc.) comme des « fuites » alors qu'ils sont correctement gitignored et jamais committés — un scan en mode filesystem produit des faux positifs sur des secrets locaux légitimement non suivis. Scanner l'historique Git évite entièrement ce problème, puisqu'il ne voit que ce qui a réellement été committé.

---

## Fraîcheur des dépendances (catégorie 11)

Distinct des audits basés sur les CVE du domaine Sécurité ci-dessus : ces outils signalent des dépendances obsolètes mais pas nécessairement vulnérables (aucune CVE déposée). Les critères détaillés de la catégorie 11 sont encore différés à la Phase 2 (voir [`docs/adr/0005-taxonomy-adjustments-deferred.md`](adr/0005-taxonomy-adjustments-deferred.md)) ; ceci n'est que la liste des outils candidats.

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| `pip list --outdated` | Natif (fait partie de pip), exécuté dans un venv éphémère, voir la décision de config ci-dessous | MIT (pip) | **Conservé**, avec la mise en garde sur le fichier de lock ci-dessous |
| `npm outdated` / `pnpm outdated` | Natif (npm/pnpm déjà présents) — `npm outdated --json` smoke-testé sur GeoChallenge-Tracker, `pnpm outdated --format json` sur HiveMind, les deux avec une sortie structurée propre | fait partie de npm/pnpm | **Conservé** |
| `composer outdated` | Natif (composer déjà présent) — `composer outdated --format=json` smoke-testé sur Summit-Stats, sortie propre, champs bonus `release-age`/`abandoned`/`latest-status` | fait partie de Composer | **Conservé** |

**Décision de config (2026-08-26, voir [`docs/adr/0012-registry-network-access-dependency-freshness.md`](adr/0012-registry-network-access-dependency-freshness.md)) :** les trois nécessitent un appel réseau vers un registre de paquets public (PyPI, npm, Packagist) pour connaître la dernière version disponible. Conditionné par le même mécanisme opt-in par run que l'accès à l'API GitHub ([0003](adr/0003-github-api-network-access.md)), en lecture seule, non activé par défaut.

**Conformité des licences (lacune catégorie 11.2, recherchée le 2026-08-26) — contrairement à la fraîcheur ci-dessus, aucun des trois n'a besoin d'un appel réseau**, puisque les métadonnées de licence sont déjà présentes dans les propres paquets installés/verrouillés de la cible — pas conditionné par D15/D6.

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| `pip-licenses` | Pas encore évalué — probablement `uvx pip-licenses --format=json`, mais nécessite que les dépendances de la cible soient réellement installées pour énumérer leurs métadonnées de licence, même précondition de venv éphémère que `pip list --outdated` (`uv export` + `uv pip install --python <scratch-venv>`) | MIT | **Conservé comme candidat**, non smoke-testé. Outil original, confirmé de nouveau activement maintenu en 2026 (nouveau mainteneur, travail d'alignement PEP 639), préféré au fork `pip-licenses-cli` puisque l'original n'est plus celui non maintenu qu'il était auparavant |
| `license-checker-evergreen` | Pas encore évalué — probablement `npx --package=license-checker-evergreen -- license-checker-evergreen --json`, lit directement les métadonnées de paquets `node_modules`, aucun appel réseau | Même licence que `license-checker` amont (famille BSD-3-Clause, à confirmer au smoke-test) | **Conservé comme candidat**, non smoke-testé. Le `license-checker` original (davglass) n'est plus maintenu depuis 2019 ; ce fork est explicitement positionné comme le remplacement drop-in activement maintenu, préféré à `license-checker-rseidelsohn` (le mainteneur se décrit lui-même comme sous-maintenu) |
| `composer licenses --format=json` | Natif (composer déjà présent, même outil déjà validé pour `composer audit`/`composer outdated`) — aucune nouvelle dépendance du tout | fait partie de Composer | **Conservé**, aucun risque de smoke-test, réutilise une commande native déjà validée |

**`pip list --outdated` nécessite un environnement résolu éphémère, pas juste le fichier de requirements (smoke-testé le 2026-08-26) :**
- Contrairement aux deux autres, `pip list --outdated` ne rapporte que sur un environnement *installé*, il n'y a aucun moyen de vérifier un `requirements.txt`/fichier de lock directement contre PyPI sans l'installer quelque part d'abord.
- Motif éphémère correct (cohérent avec D7) : `uv export --frozen --no-hashes -o <scratch>/reqs.txt` (export en lecture seule depuis le propre `uv.lock` de la cible) → `uv pip install --python <scratch-venv> -r <scratch>/reqs.txt` → `uv pip list --python <scratch-venv> --outdated`. Vérifié sur Triton (a un `uv.lock`) : rapporte correctement pinné-vs-dernier pour les 70 paquets.
- **Piège trouvé et évité :** `uv sync --python <scratch-venv>` ne respecte **pas** `--python` de la même façon que `uv pip install` — il installe toujours dans le propre `.venv` du dépôt cible (aurait écrit dans Triton si aucun `.venv` n'y existait encore). Ne pas utiliser `uv sync` pour cette vérification ; utiliser `uv export` + `uv pip install --python` à la place, qui reste entièrement dans le venv scratch.
- **Limitation :** cette vérification n'est significative que pour les dépôts avec un vrai fichier de lock (`uv.lock`, `poetry.lock`, ou `requirements.txt` avec des pins `==` exacts). Smoke-testé sur JobFlow (contraintes `>=` lâches, aucun fichier de lock) : une installation `uv pip install` éphémère depuis `requirements.txt` résout toujours vers la dernière version satisfaisant la contrainte, donc `pip list --outdated` sur cette installation fraîche est trivialement vide, il n'y a rien de pinné à comparer contre le registre. Pour les dépôts non pinnés, ce critère devrait rapporter `N/A` plutôt qu'un faux « à jour ».

---

## Python

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| Ruff | `uvx ruff check --output-format=json` — fonctionne directement | MIT | **Conservé** |
| mypy | `uvx mypy --ignore-missing-imports` — fonctionne directement **seulement quand la cible n'a aucun plugin mypy configuré**. Smoke-testé sur GeoChallenge-Tracker (pilote Phase 3, 2026-08-26) : échoue franchement (`Error importing plugin "pydantic.mypy": No module named 'pydantic'`) parce que son `pyproject.toml` déclare le plugin `pydantic.mypy` — mypy avait besoin des propres dépendances runtime de la cible installées (`uvx --with-requirements requirements.txt --with mypy mypy ...`, même motif éphémère que pytest) pour le résoudre | MIT | **Conservé**, avec une règle de détection : vérifier d'abord `pyproject.toml`/`mypy.ini` pour une entrée `plugins = [...]` ; si présente, exécuter avec `--with-requirements`, pas `uvx mypy` nu |
| pytest | `uvx --with-requirements requirements.txt pytest ...` — fonctionne, collecte/exécute correctement les propres tests du dépôt cible | MIT | **Conservé**, avec une distinction notée ci-dessous |
| coverage | `uvx coverage` — fonctionne directement | Apache 2.0 | **Conservé** |
| radon (complexité) | `uvx radon cc --json` — fonctionne directement, sortie structurée de complexité cyclomatique avec rang | MIT | **Conservé** |
| vulture (code mort) | Pas encore évalué — probablement `uvx vulture <path>`, même motif éphémère que radon | MIT | **Conservé comme candidat**, non smoke-testé ; activement maintenu (versions 2026), rapporte une confiance par constat (60-100%) qui vaut la peine d'être remontée telle quelle plutôt que lissée, selon sa propre limitation documentée d'analyse statique (peut manquer du code appelé implicitement) |
| docvet (couverture docstring, lacune catégorie 5.3) | Pas encore évalué — probablement `uvx docvet <path>`, même motif éphémère | MIT | **Conservé comme candidat**, non smoke-testé. Préféré à `interrogate` (plus ancien, plus établi, mais un outil concurrent de 2026 affirme explicitement qu'il n'est pas maintenu, à vérifier directement contre l'activité de commit récente de `econchick/interrogate` avant de faire confiance à l'un ou l'autre). docvet est plus récent/moins éprouvé mais activement publié en 2026 et couvre la présence + le caractère périmé (git-diff/blame) plutôt que la présence seule |

**Distinction notée :** contrairement à Ruff/mypy (analyse statique pure, ont seulement besoin de la source de la cible), pytest/coverage ont besoin que les **propres dépendances runtime** du dépôt cible soient installées pour réellement exécuter sa suite de tests — c'est inévitable, pas une violation de D7. D7 ne pinne que la version de **l'outil d'audit lui-même** ; les versions de dépendances de la cible pour exécuter ses tests viennent de son propre lockfile/`requirements.txt`, exactement comme prévu. L'installation éphémère de ces dépendances fonctionne via `uvx --with-requirements <file> pytest ...`.

**Règle inter-langages — ne jamais faire confiance à un artefact de couverture committé (Summit-Stats, second pilote, 2026-08-27) :** un `coverage.xml` committé à la racine du dépôt Summit-Stats montrait 73,97% de couverture d'instructions, en dessous du gate CI à 80% du dépôt lui-même — un constat d'apparence réelle. Relancer `vendor/bin/pest --coverage` fraîchement a produit 91,4% ; le fichier committé était simplement périmé, pas régénéré depuis un point antérieur de l'historique du dépôt. Ceci s'applique à tout langage/outil pouvant produire un rapport de couverture (`coverage.xml` ici, mais également `coverage-summary.json` pour Vitest/Jest, `.coverage` pour `coverage.py` de Python) : la preuve de couverture 3.1/3.4 doit toujours provenir d'une **exécution de test en direct effectuée par l'audit lui-même**, jamais de la lecture d'un fichier de rapport committé, même quand il est présent et semble plausible.

---

## JavaScript / TypeScript

Smoke-testé sur GeoChallenge-Tracker (Vue 3 + TS, `node_modules` déjà installé localement).

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| ESLint | `npx eslint . --format json` — se résout vers le propre binaire/config ESLint local du dépôt (`node_modules/.bin/eslint`), sortie JSON propre. **Mise en garde de périmètre trouvée au pilote Phase 3 (GeoChallenge-Tracker, 2026-08-26) :** un `.` nu à la racine du dépôt a ramassé `backend/.venv/lib/.../coverage_html.js` et `backend/htmlcov/coverage_html_cb_*.js` (gitignored, artefacts générés de la chaîne d'outils Python, pas du code source) comme 42 erreurs faux positifs, parce que le propre `eslint.config.js` du dépôt n'ignore que les chemins que son propre script `npm run lint` scanne réellement (`frontend/src frontend/tests`), pas l'arbre entier — même classe de piège que le problème de découverte de Dockerfile ci-dessous | MIT | **Conservé**, mais invoqué avec le périmètre de chemin du propre script `lint` du dépôt (lire la cible `scripts.lint` de `package.json`), pas un `.` nu |
| `tsc --noEmit` | `npx tsc --noEmit` — fonctionne, code de sortie 0/non-zéro, pas de rapporteur JSON natif (sortie texte, format `file(line,col): error TSxxxx: message`, nécessite un parsing texte) | Apache-2.0 | **Conservé** |
| knip (dépendances/exports morts) | `npx knip --reporter json` — téléchargement éphémère via npx, tableau JSON `issues` propre. **Deux mises en garde trouvées au pilote Phase 3 (GeoChallenge-Tracker, 2026-08-26) :** (1) sans config `entry`/`project`, knip a signalé les vrais points d'entrée Vue (`App.vue`, `main.ts`) comme `files` inutilisés — un mode de faux positif connu pour les projets non configurés ; (2) le stdout a été pollué par les propres effets de bord `console.log` de la cible (depuis `playwright.config.ts`, évalué pendant la découverte de config de knip) affichés *avant* le payload JSON — le parsing doit localiser le premier préfixe `{"issues"` plutôt que `json.loads(stdout)` directement | ISC | **Conservé**, avec un `knip.json` minimal détenu par l'audit (globs `entry`/`project`) par dépôt basé sur Vite, et une extraction défensive du payload JSON depuis stdout |
| Vitest | `npx vitest run --reporter=json` — fonctionne, collecte/exécute correctement la propre suite de tests du dépôt cible (419/419 réussis sur GeoChallenge-Tracker), JSON propre | MIT | **Conservé**, même distinction de dépendance runtime que pytest/coverage ci-dessus |
| Playwright | Présent comme script `test:e2e`, nécessite `build:test` + un serveur actif + des navigateurs installés d'abord — plus lourd et plus statefull qu'un outil d'audit statique | Apache-2.0 | **Conservé comme candidat**, non smoke-testé cette session ; stratégie d'invocation (étape de build, serveur éphémère, headless uniquement) différée à la définition de critère Phase 2 |

**Note sur le respect de la config ESLint :** selon l'intention de la liste de candidats (`docs/system-design.md#12`), ESLint s'exécute avec la **propre** config du dépôt cible comme *donnée d'entrée*, pas surchargée par le système d'audit — l'audit mesure si le propre linter du dépôt (quelles que soient les règles qu'il déclare) passe, pas s'il correspond à un style maison externe.

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| Règle ESLint `complexity`, config détenue par l'audit (complexité cyclomatique, lacune catégorie 2.3/5.1/15.2) | Pas encore évalué — même binaire ESLint déjà validé ci-dessus, invoqué avec une config **rédigée par l'audit** (`--no-eslintrc -c <audit-config>`) activant seulement la règle `complexity`, indépendante du propre `.eslintrc` du dépôt | MIT (ESLint) | **Conservé comme candidat**, non smoke-testé. Délibérément pas la propre config de la cible ici (contrairement à 2.1/2.2 ci-dessus), même logique « détenu par l'audit, indépendant de la config » déjà appliquée à radon pour Python, afin qu'un dépôt ne puisse pas gonfler son score de complexité juste en ne configurant pas la règle. Alternative rejetée : les paquets npm dédiés (ex. `cyclomatic-complexity`) sont plus récents, moins établis, licence non confirmée — réutiliser le binaire ESLint déjà validé est moins risqué |

| Spectral (linting de contrat OpenAPI, lacune catégorie 10.2) | Pas encore évalué — `npx --package=@stoplight/spectral-cli -- spectral lint <spec-file> --format json`, le ruleset intégré `spectral:oas` couvre OpenAPI v2/v3 | Apache 2.0 | **Conservé comme candidat**, non smoke-testé. Précondition plus légère que Lighthouse/mdn-http-observatory : nécessite un fichier de spec OpenAPI déjà exporté (FastAPI : appeler `app.openapi()`, nécessite les propres dépendances runtime de la cible installées, même classe de précondition que pytest ; Laravel : une commande de génération artisan via L5-Swagger), pas un serveur actif |

**Couverture de docstring (lacune catégorie 5.3) : aucun candidat trouvé pour JS/TS.** Les outils de « couverture » existants dans cet écosystème (`type-coverage`, `typescript-coverage-report`) mesurent la couverture de *type* TypeScript, pas la *présence de commentaire* JSDoc, une métrique différente, pas un substitut. Reste une lacune ouverte, pas un candidat en attente de smoke-test.

---

## PHP

Smoke-testé sur Summit-Stats (Laravel + Pint + Pest, le seul dépôt PHP du périmètre).

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| PHPStan (+ Larastan pour les cibles Laravel) | **Pas** une installation éphémère/façon-D7 pour les cibles Laravel — voir la décision de config résolue ci-dessous, une exception confirmée à D7 | MIT | **Conservé**, décision de config résolue ci-dessous |
| Laravel Pint | Natif (déjà une devDependency de Summit-Stats) — `vendor/bin/pint --test --format=json` → `{"result":"pass"}` propre | MIT | **Conservé** |
| Pest (construit sur PHPUnit) | Natif (déjà une devDependency de Summit-Stats) — `vendor/bin/pest --testsuite=Unit --log-junit=<file>` → 71/71 réussis, XML JUnit standard (pas de rapporteur JSON natif, même situation de parsing texte/XML que `tsc`) | MIT (Pest) / BSD-3-Clause (PHPUnit) | **Conservé** |
| PHPMD (complexité + code mort, lacune catégorie 2.3/5.1/15.2) | Smoke-testé sur Summit-Stats (second pilote, 2026-08-27), installation Composer isolée éphémère (propre projet scratch, voir mise en garde ci-dessous), `vendor/bin/phpmd <path> xml codesize,unusedcode` (le rapporteur `json` n'existe pas — PHPMD ne supporte que `xml`/`text`/`html`) → 3 constats réels : 1 méthode exactement au seuil de complexité cyclomatique 10, 1 classe à complexité 54 vs un seuil de 50, 1 variable locale inutilisée. Le rapport signal/bruit était bon, aucun faux positif trouvé | BSD | **Conservé**, validé |
| php-censor/phpdoc-checker (couverture docblock, lacune catégorie 5.3) | Pas encore évalué — probablement installation Composer isolée éphémère (même motif que PHPStan), `vendor/bin/phpdoc-checker` avec sortie JSON | BSD-2-Clause | **Conservé comme candidat**, non smoke-testé. Fork de l'original `dancryer/php-docblock-checker`, vérifie la présence de docblock sur les classes/méthodes |

**Décision de config résolue (Summit-Stats, second pilote, 2026-08-27) :** PHPStan au niveau par défaut 5 sans extension Laravel-aware a levé 87 constats sur `app/` de Summit-Stats, le gros étant des faux positifs sur les propriétés/méthodes magiques Eloquent et les helpers globaux Laravel (`Function config not found`, `Access to an undefined property App\Models\Activity::$id`) que PHPStan ne peut pas résoudre sans les métadonnées de modèle dynamiques et les stubs de helpers de Laravel. Le correctif est `larastan/larastan`, mais il **ne peut pas** être installé de la même façon que PHPStan seul (le projet scratch éphémère entièrement isolé façon D7) : le faire échoue franchement avec `Undefined constant "Larastan\Larastan\LARAVEL_VERSION"`, parce que Larastan résout la version Laravel de la cible et charge son jeu de stubs en introspectant le propre `vendor/`/`composer.lock` **installé** de l'app — un projet Composer scratch sans rapport n'a aucun contexte de ce type à introspecter, quel que soit le chemin passé à `--paths`.

Ce n'est **pas** une question de périmètre de scan — exclure `vendor/`/les dossiers de framework des `paths` analysés n'y change rien, parce que l'échec se produit au moment du parsing de config `extension.neon` de Larastan, avant même qu'un seul fichier ne soit sélectionné pour analyse. Le seul correctif fonctionnel, confirmé par test direct : ajouter temporairement `larastan/larastan` comme `require-dev` dans le propre `composer.json` **du dépôt cible** (`composer require --dev phpstan/phpstan larastan/larastan --no-interaction`), exécuter `vendor/bin/phpstan` depuis là avec un include `extension.neon`, puis annuler `composer.json`/`composer.lock` et relancer `composer install` pour restaurer le dépôt à son état d'origine. Résultat confirmé sur Summit-Stats : 87 file_errors majoritairement du bruit sont tombés à 12 file_errors de signal réel (une constante de classe inutilisée, des discordances de type générique sur les types de retour de relation Eloquent, un problème potentiel d'appel null-safe, des avertissements de paramètre par référence). C'est une exception réelle et documentée à la règle D7 « l'outil d'audit est toujours indépendant de l'outillage propre de la cible » — l'analyse statique Laravel-aware nécessite structurellement de s'exécuter à l'intérieur de l'arbre de dépendances de la cible. Toute orchestration future doit annuler le `composer.json`/`composer.lock` de la cible ensuite afin que l'audit ne laisse jamais d'empreinte dans le dépôt scanné.

**Règle du scratch isolé par outil (Summit-Stats, second pilote, 2026-08-27) :** pour les outils qui peuvent réellement rester dans un projet scratch éphémère façon D7 (PHPMD, et PHPStan simple non-Laravel), chaque outil a besoin de son **propre** projet Composer scratch, jamais partager un `vendor/` entre plusieurs outils PHP éphémères. Installer PHPMD dans un dossier scratch qui avait déjà PHPStan+Larastan a causé un conflit de dépendances Composer fatal (`PDepend\DependencyInjection\PdependExtension::load(...)` incompatible avec la version Symfony DI que l'arbre de Larastan a tirée) — pas un bug de PHPMD, un clash transitif entre les arbres de dépendances de deux outils sans rapport partageant un `vendor/`. Un projet scratch frais, PHPMD uniquement, s'est résolu proprement.

**Note sur l'installation native de Pint/Pest :** contrairement à PHPStan (détenu par le système d'audit, éphémère, indépendant de la cible), Pint et Pest ici sont les propres devDependencies pinnées du dépôt cible, exécutées nativement via `vendor/bin/`, le même motif déjà validé pour `composer audit`/`composer outdated`. C'est intentionnel, pas une incohérence : les outils de style/test mesurent *le comportement propre configuré du dépôt*, le même raisonnement déjà appliqué à ESLint ci-dessus, alors que PHPStan (et Ruff/mypy) sont de l'analyse statique externe pure, exécutée à une version contrôlée par le système d'audit afin que la stabilité des scores (D7) ne dépende pas du fait que le dépôt cible se donne la peine de pinner/mettre à jour son propre linter.

---

## Duplication de code (lacune catégorie 2.5, inter-langages)

Contrairement aux lacunes de complexité/code mort ci-dessus (outil séparé par langage), un seul candidat couvre tout le mélange de langages du portfolio.

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| jscpd | Pas encore évalué — probablement `npx --package=jscpd -- jscpd <path> --reporters json` (v4, basé Node) ou un binaire Rust v5 préconstruit (aucun runtime Node nécessaire) | MIT (à confirmer au smoke-test) | **Conservé comme candidat**, non smoke-testé. Outil unique pour Python/JS-TS/PHP/Vue (223+ langages via des grammaires Prism), largement adopté (Microsoft, Salesforce, intégré dans super-linter/Codacy), activement développé en 2026 (réécriture Rust v5, 24-37x plus rapide que v4). Alternative rejetée : PMD-CPD couvre aussi Python/PHP/JS, mais nécessite un runtime JVM, une classe de dépendance supplémentaire qu'aucun autre outil de cette chaîne ne requiert (uvx/npx/composer/Docker uniquement), sans avantage clair sur jscpd pour les langages de ce portfolio |

---

## Architecture / dépendances (sous-périmètre catégorie 11 : cycles, layering)

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| madge (JS/TS, proposé à l'origine) | `npx --package=madge -- madge --extensions ts --json <dir>` — fonctionne proprement sur un sous-arbre TS pur (`frontend/src/utils` sur GeoChallenge-Tracker), mais **échoue durement** avec un crash du parseur dès que l'arbre scanné inclut un SFC `.vue` (confirmé sur `frontend/src`) | MIT | **Rejeté** — aucun support natif des SFC Vue, et les trois dépôts JS/TS du périmètre (GeoChallenge-Tracker, HexaRot, HiveMind) sont basés sur Vue |
| dependency-cruiser (remplacement) | `npx --package=dependency-cruiser -- depcruise --no-config --include-only "^frontend/src" --output-type json <dir>` — fonctionne proprement sur l'arbre complet, reconnaît correctement les SFC `.vue` comme nœuds de graphe (26/109 modules sur GeoChallenge-Tracker), rapporte `circular`/`orphan` par module | MIT | **Conservé**, remplace madge côté JS/TS |
| pydeps (Python) | `uvx pydeps <package> --show-deps --no-output --max-bacon=0` (ou `--show-cycles`) — fonctionne directement, JSON structuré, testé sur le package `engine` de Triton | Apache 2.0 | **Conservé** |
| import-linter (Python) | `uvx import-linter` — s'exécute, mais c'est un outil d'**application de règles**, pas un détecteur de cycle générique : il ne fait rien sans une config `.importlinter`/`setup.cfg` rédigée par la cible déclarant des « contrats » architecturaux (couches). Aucun dépôt Python du périmètre (Triton, JobFlow, Stamped) n'en définit un | Apache 2.0 | **Rejeté** pour la chaîne d'outils générique du portfolio — rien à évaluer sans config rédigée par le dépôt ; à revisiter par dépôt seulement si l'un ajoute un fichier de contrat plus tard |
| deptrac (PHP) | Installation éphémère via projet Composer isolé (même motif que PHPStan) — `deptrac analyse` nécessite une config `deptrac.yaml`/`depfile.yaml` rédigée par la cible déclarant des couches. Summit-Stats n'en a aucune ; confirmé via une erreur `CannotLoadConfiguration` | MIT | **Rejeté** pour la chaîne d'outils générique du portfolio, même raisonnement qu'import-linter |

**Quasi-incident trouvé pendant ce smoke test :** `npx depcruise` (nom de binaire nu) a failli se résoudre vers un paquet npm sans rapport littéralement nommé `depcruise` — confirmé via `npm view depcruise` être un *placeholder de confusion de dépendances* enregistré (`🚫 Placeholder to prevent dependency confusion`, publié spécifiquement pour squatter le nom de binaire avant de mauvais acteurs), pas le vrai outil `dependency-cruiser`. Aucun mal fait ici puisque le placeholder est inerte, mais cela démontre que le risque décrit dans la règle de sécurité npx en haut de ce document était réel, pas théorique. Toutes les invocations `npx` éphémères de ce document (passées et futures) doivent utiliser `--package=<nom-exact> --`.

**Motif pour import-linter/deptrac à l'avenir :** les deux outils sont légitimes et méritent d'être reproposés comme critère *opt-in* en Phase 2, par exemple « si ce dépôt définit son propre fichier de contrat architectural, est-il respecté ? », plutôt qu'une vérification générique à l'échelle du portfolio, puisque rédiger le contrat lui-même est une décision de conception spécifique au dépôt que le système d'audit ne devrait pas prendre au nom du développeur.

---

## Conteneurs

Les deux outils sont des binaires Go/Haskell sans wrapper `uvx`/`npx` — exécutés via Docker, selon D7.

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| Hadolint (lint Dockerfile) | `docker run --rm -i hadolint/hadolint hadolint --format json - < Dockerfile` — smoke-testé sur le `backend/Dockerfile` de GeoChallenge-Tracker, 3 constats plausibles peu bruyants (versions `apt-get`/`pip` non pinnées, `--no-cache-dir` manquant) | **GPL-3.0** | **Conservé**, note de licence ci-dessous |
| Trivy (scan d'image) | `docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --format json --severity HIGH,CRITICAL --scanners vuln <image>` — smoke-testé contre l'image locale déjà construite `geochallenge-tracker-backend:latest`, trouvé 194 CVE HIGH/CRITICAL de paquets OS Debian + 7 de paquets Python, plausible | Apache 2.0 | **Conservé**, nécessite l'accès au socket du démon Docker local |

**Note de licence :** Hadolint est GPL-3.0, plus stricte (copyleft) que tout autre outil validé jusqu'ici (MIT/Apache/BSD/ISC). Sans conséquence ici : le système d'audit ne fait qu'*invoquer* Hadolint comme sous-processus externe via sa propre image Docker, il ne lie ni n'embarque jamais le code de Hadolint dans le propre code du système d'audit, donc les clauses de copyleft/distribution de la GPL ne s'appliquent pas. Aucune différence de principe avec l'appel de n'importe quel autre outil CLI.

**Précondition du scan d'image :** contrairement à Hadolint (fonctionne sur la source du Dockerfile, toujours disponible), `trivy image` a besoin d'une image déjà **construite**. Cela a été testé ici contre une image déjà présente depuis un usage local antérieur de `docker compose` — le système d'audit ne construit **pas** d'images lui-même en effet de bord d'un scan (ce serait une étape plus lourde et plus invasive qu'un outil d'audit statique/config-only ne devrait prendre). Si un dépôt n'a aucune image construite localement au moment de l'audit, cette vérification devrait rapporter `N/A` plutôt que de déclencher une construction.

**Piège de découverte Dockerfile/compose trouvé (2026-08-26) :** un `find . -iname Dockerfile*` naïf sur Summit-Stats a remonté 9 Dockerfiles, la plupart du bruit : `vendor/laravel/sail/runtimes/*/Dockerfile` (internes d'un paquet tiers, pas l'infra propre du dépôt) et des doublons sous `.claude/worktrees/*/vendor/...` (une copie de worktree périmée). La découverte doit exclure `vendor/`, `node_modules/`, et tout répertoire imbriqué de type worktree `.git`, en ne scannant que les Dockerfiles propres de premier niveau/de service du dépôt, pas les copies vendorées ou dupliquées.

**Généralisé en une règle d'orchestration à l'échelle du portfolio (second pilote, Summit-Stats, 2026-08-27) :** le même répertoire `.claude/worktrees/` a indépendamment cassé deux autres outils sur ce dépôt, confirmant que le piège ci-dessus n'est pas spécifique aux Dockerfiles : (1) le `test.exclude` par défaut de Vitest couvre `node_modules/**` et `e2e/**` à la racine du dépôt mais pas une copie de worktree imbriquée des mêmes chemins, comptant silencieusement chaque test deux fois (62 réels → 124 rapportés) ; pire, `npm run test:coverage` (sans filtre de chemin) a **échoué durement** avec `Playwright Test did not expect test.describe() to be called here` parce que Vitest a ramassé un fichier de spec Playwright dupliqué à l'intérieur du worktree — un échec complet du run, pas juste des comptages bruyants ; (2) le scan filesystem de Trivy (`trivy fs`) a compté deux fois des CVE depuis `composer.lock`/`package-lock.json` dupliqués à l'intérieur du worktree.

**C'est directement filtrable par outil — aucun fallback manuel/skip-tool nécessaire.** Chaque outil de cette chaîne qui parcourt récursivement le système de fichiers a un mécanisme d'exclusion natif, confirmé en vérifiant la CLI de chacun : `find` (`-not -path '*/pattern/*'`), Vitest (`--exclude <glob>`), `trivy fs`/`trivy image` (`--skip-dirs`), dependency-cruiser (`-x/--exclude <regex>`), ESLint (`--ignore-pattern`), PHPMD (`--exclude`, motifs glob séparés par virgule), PHPStan (`parameters.excludePaths` dans sa config neon, pas de flag CLI, mais trivial à ajouter à la config que l'audit génère déjà). **Le motif d'exclusion ne doit pas être codé en dur sur `.claude/worktrees`** — c'est juste là que les worktrees de ce pilote spécifique se trouvaient. L'implémentation correcte et générale consiste à exécuter `git worktree list --porcelain` contre le dépôt cible d'abord, extraire chaque chemin de worktree sauf le principal, et injecter ces chemins dans le mécanisme d'exclusion que l'outil invoqué supporte. C'est un correctif d'orchestration pur (calculer la liste d'exclusion une fois par dépôt, la transmettre à chaque appel d'outil récursif) — la Phase 4 devrait l'implémenter comme une étape partagée, pas un cas particulier par outil.

---

## Performance (frontend uniquement — catégorie 6, voir `docs/quality-framework.md`§4.6)

La performance backend/BDD est délibérément exclue du Quality Framework v1.0 (aucune définition objective sans un SLA par projet), pas une lacune d'outillage, aucun candidat évalué ici. Le frontend a un candidat plausible, listé pour validation déclenchée en Phase 2, pas encore smoke-testé cette session.

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| Lighthouse | Pas encore évalué — probablement `npx --package=lighthouse -- lighthouse <url> --output json`, même classe de précondition que Playwright (nécessite un serveur actif, une étape de build, Chrome headless) | Apache 2.0 | **Conservé comme candidat**, non smoke-testé ; doutes ouverts connus (reproductibilité du score d'une exécution à l'autre, périmètre étroit limité au temps de chargement) portés dans `quality-framework.md`§4.6, à revisiter avant que ce critère ne soit fiable à plus que confiance MOYENNE |

---

## Git / CI

| Outil | Disponibilité | Licence | Verdict |
|---|---|---|---|
| actionlint | Aucun wrapper `uvx`/`npx` (binaire Go) — via Docker : `docker run --rm -v <repo>:/repo -w /repo rhysd/actionlint:latest -format '{{json .}}'` — découvre automatiquement `.github/workflows/` sans argument de chemin nécessaire, smoke-testé sur GeoChallenge-Tracker, 2 constats réels (problème `shellcheck` embarqué : variable non guillemetée permettant le globbing/word-splitting dans une étape `run:`) | MIT | **Conservé** |
| Protection de branche / exigences de revue de PR / historique d'exécution des Actions | Non dérivable du `.git` local — nécessite l'API GitHub | — | Différé à D6 (accès API GitHub opt-in, en lecture seule), ne fait pas partie de la chaîne d'outils statique locale |

**Bonus trouvé :** actionlint intègre l'analyse `shellcheck` pour les scripts shell `run:` en ligne à l'intérieur des étapes de workflow, donc un seul outil attrape à la fois les problèmes de syntaxe YAML-workflow et les problèmes de scripting shell dans les scripts embarqués, sans avoir besoin d'une invocation shellcheck séparée.

---

## Hooks pre-commit (alimente le critère D12 : matrice de couverture)

Pas un simple outil « exécuter et obtenir des constats » — D12 a besoin du **contenu** de la couverture (quels types de validateurs couvrent quels domaines), pas juste la présence/absence d'un framework de hooks. Smoke-testé en lisant de vraies configs à travers les dépôts du périmètre qui utilisent chaque framework : `.pre-commit-config.yaml` (5 dépôts : CC-Beacon, GeoChallenge-Tracker, JobFlow, Stamped, Triton) et `.husky/` (3 dépôts : HexaRot, HiveMind, Summit-Stats). Aucun dépôt du périmètre n'utilise `lefthook.yml`.

| Framework | Extraction de preuve | Verdict |
|---|---|---|
| `pre-commit` (écosystème Python) | La config est entièrement déclarative dans `.pre-commit-config.yaml` — l'`id`/`name` et le regex `files` de chaque hook donnent directement des paires (type de validateur, domaine). `uvx pre-commit validate-config` confirme que le fichier est valide selon le schéma (exit 0 sur GeoChallenge-Tracker) comme vérification de bon sens peu coûteuse avant le parsing | **Conservé** — le parsing YAML seul suffit, pas besoin d'exécuter réellement les hooks |
| `husky` | **Pas autonome.** `.husky/pre-commit` est typiquement un wrapper shell d'une ligne (`npx lint-staged` à la fois sur HexaRot et Summit-Stats) — il ne nomme *aucun* validateur lui-même. La vraie matrice (type de validateur × domaine) vit un cran plus loin, dans la clé `"lint-staged"` de `package.json` (motif glob → liste de commandes par motif) | **Conservé**, mais l'extraction **doit chaîner deux fichiers** : `.husky/<hook-name>` → confirmer qu'il délègue à `lint-staged` → puis lire la clé `lint-staged` de `package.json` pour la matrice réelle. Lire `.husky/` seul donne un faux signal « couvert » ou « vide » |
| `lefthook` | Aucun dépôt du périmètre ne l'utilise — le format de config (`lefthook.yml`) est du YAML déclaratif comme `pre-commit`, donc la même approche de parsing direct devrait s'appliquer, mais c'est **non vérifié**, pas smoke-testé | **Conservé comme candidat**, à vérifier contre une vraie config si/quand une apparaît dans le périmètre |

**Résultats concrets de matrice de couverture trouvés (utiles comme exemples travaillés pour la définition du critère D12 en Phase 2) :**
- GeoChallenge-Tracker (`.pre-commit-config.yaml`) : le backend a ruff (lint) + ruff-format (format) + mypy (type-check) ; le frontend a prettier (format) + eslint (lint) + vue-tsc (type-check) — matrice complète, les 6 cellules applicables couvertes.
- HexaRot (husky → lint-staged) : backend et frontend ont tous deux eslint (lint) uniquement — aucun hook de format ou type-check sur l'un ou l'autre domaine, 2/6 cellules couvertes.
- Summit-Stats (husky → lint-staged) : le frontend a eslint (lint) + prettier (format) ; le backend PHP a Pint (format uniquement, aucun PHPStan câblé dans le hook) — 3/6 cellules couvertes (en utilisant le modèle à 3 types de validateur ; Pint chevauche lint/format en pratique pour PHP, mérite une note de définition en Phase 2).

---
