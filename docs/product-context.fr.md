# Contexte produit

> Version française | [English version](product-context.md)

Contexte produit minimal. Pour le raisonnement de conception complet, voir
[`docs/system-design.md`](system-design.md) ; pour les critères d'audit
eux-mêmes, voir [`docs/quality-framework.md`](quality-framework.md).

## Ce que c'est

Portfolio Engineering Radar est un système d'audit local, offline-first,
pour un portfolio personnel de dépôts logiciels. Il exécute un ensemble
fixe de vérifications d'analyse statique et d'outillage sur chaque dépôt,
normalise les résultats bruts en constats scorés par rapport au Quality
Framework, et est destiné à alimenter un dashboard et une roadmap
d'amélioration vivante.

## Pour qui

Un seul développeur auditant ses propres dépôts. Il n'y a pas
d'enjeu multi-tenant ou multi-utilisateur : le public visé est une seule
personne décidant où investir l'effort de qualité d'ingénierie en priorité
sur un portfolio de projets.

## Pourquoi ce système existe

Suivre manuellement la santé technique de nombreux side projects ne passe
pas à l'échelle ; les constats sont oubliés et la qualité dérive de façon
inégale entre les dépôts. Le système existe pour rendre cette dérive
visible, comparable entre dépôts, et actionnable via des éléments de
roadmap priorisés, sans exiger que les dépôts audités changent quoi que
ce soit à eux-mêmes.

## Périmètre actuel

- Moteur d'audit (`radar-audit`) et modèle de données (`radar-core`) : en cours, voir [`docs/roadmap.md`](roadmap.fr.md)
- Dashboard et génération de rapports : pas encore commencés
