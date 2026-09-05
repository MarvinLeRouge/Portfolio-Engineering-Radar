[🇫🇷 Version française](SECURITY.fr.md) | 🇬🇧 English version

---

# Security Policy

## Supported Versions

This project follows a single rolling `main` branch. There are no maintained release branches; only the latest commit on `main` is supported.

## Reporting a Vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, use GitHub's private vulnerability reporting: go to the [Security tab](https://github.com/MarvinLeRouge/Portfolio-Engineering-Radar/security/advisories/new) of this repository and click "Report a vulnerability". This keeps the report private until a fix is available.

This project is maintained by a single developer, so response times are best-effort rather than guaranteed on an SLA.

## Scope

In scope: the `radar-core` and `radar-audit` packages, their dependency manifests, and the CI configuration in this repository.

Out of scope: the target repositories that `radar-audit` reads and analyzes when run against a local portfolio checkout — vulnerabilities in those repositories should be reported to their own maintainers, not here.
