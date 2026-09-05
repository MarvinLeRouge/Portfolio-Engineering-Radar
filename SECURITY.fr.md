🇫🇷 Version française | [🇬🇧 English version](SECURITY.md)

---

# Politique de sécurité

## Versions supportées

Ce projet suit une unique branche `main` glissante. Il n'y a pas de branches de release maintenues ; seul le dernier commit sur `main` est supporté.

## Signaler une vulnérabilité

Merci de **ne pas** ouvrir d'issue GitHub publique pour une vulnérabilité de sécurité.

Utilisez plutôt le signalement privé de vulnérabilités de GitHub : rendez-vous sur l'onglet [Security](https://github.com/MarvinLeRouge/Portfolio-Engineering-Radar/security/advisories/new) de ce dépôt et cliquez sur "Report a vulnerability". Le signalement reste privé jusqu'à ce qu'un correctif soit disponible.

Ce projet est maintenu par un développeur unique, les délais de réponse sont donc du meilleur effort, sans SLA garanti.

## Périmètre

Dans le périmètre : les packages `radar-core` et `radar-audit`, leurs manifestes de dépendances, et la configuration CI de ce dépôt.

Hors périmètre : les dépôts cibles que `radar-audit` lit et analyse lors d'un audit de portfolio local — les vulnérabilités de ces dépôts doivent être signalées à leurs propres mainteneurs, pas ici.
