[🇫🇷 Version française](CONTRIBUTING.fr.md) | 🇬🇧 English version

---

# Contributing to Portfolio Engineering Radar

This is primarily a personal project. External contributions (bug reports, fixes, small improvements) are welcome but limited in scope.

## Prerequisites

- Python 3.12+
- [`uv`](https://docs.astral.sh/uv/) for dependency management

## Local setup

```bash
git clone https://github.com/MarvinLeRouge/Portfolio-Engineering-Radar.git
cd Portfolio-Engineering-Radar
uv sync
uv run pre-commit install
```

## Running tests

```bash
uv run --package radar-core pytest
uv run --package radar-audit pytest
```

## Workflow

1. Fork the repository and create a branch off `main`.
2. Make your change, with tests covering it.
3. Commit following the convention below.
4. Push and open a pull request against `main`.
5. Pre-commit hooks (see below) must pass before review.

## Branch naming

| Type | Prefix |
|---|---|
| Feature | `feat/short-description` |
| Bug fix | `fix/short-description` |
| Chore | `chore/short-description` |
| Documentation | `docs/short-description` |
| Refactor | `refactor/short-description` |
| Tests | `test/short-description` |

Use lowercase kebab-case. No special characters.

## Commit convention

Follow [Conventional Commits](https://www.conventionalcommits.org/), imperative mood, lowercase summary, no trailing period, with a mandatory `Modified files:` section:

```
<type>(<optional scope>): <short summary>

Modified files:
- path/to/file-a.ext - what was changed
- path/to/file-b.ext - what was changed
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`, `ci`.

## Code style

`ruff` (lint + format) and `mypy --strict` run on `radar-core` and `radar-audit` via pre-commit hooks (`.pre-commit-config.yaml`). There is no CI pipeline yet enforcing these remotely (see [`docs/roadmap.md`](docs/roadmap.md)) — run `uv run pre-commit run --all-files` locally before opening a pull request.

## Code of Conduct

This project follows a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold it.

## License

By contributing, you agree that your contributions will be licensed under the project's license (see [LICENSE](LICENSE)).
