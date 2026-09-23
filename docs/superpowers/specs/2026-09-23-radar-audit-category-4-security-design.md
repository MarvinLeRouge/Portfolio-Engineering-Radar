# radar-audit — Category 4 (Security) Runners (Increment 2.4) — Design

> Status: draft, pending review.
> Context: Phase 4, sub-project 2/4 (`radar-audit`). Builds on increments 2.1-2.3 (categories 1-3), all merged to `main`.
> Spec references: `docs/quality-framework.md`§4.4 (criteria catalog), §3.2 (critical penalties P1/P2), §3.3 (N/A handling), `docs/toolchain.md` (Security section, Containers section), `docs/superpowers/specs/2026-09-01-radar-audit-category-3-testing-reliability-design.md` (structural precedent).

---

## 1. Scope

Fourth of the fifteen category increments (2.1-2.15, strict numeric order). Covers **category 4, Security**:

| # | Criterion (exact taxonomy name) | Archetype | Tool(s) | In this increment? |
|---|---|---|---|---|
| 4.1 | Dependency vulnerabilities (CVE) | A | pip-audit / `pnpm audit` / `composer audit` | Yes |
| 4.2 | Secrets in tracked history | A | Gitleaks (git-history mode) | Yes |
| 4.3 | SAST findings | A | Semgrep | Yes |
| 4.4 | Container image vulnerabilities | A | Trivy (image scan) | Yes |
| 4.5 | Dockerfile hardening | B | Hadolint | Yes |
| 4.6a | AuthN/authZ hygiene | A | Semgrep `p/security-audit` + framework rulesets | **No — deferred** |
| 4.6b | HTTP security headers | A | mdn-http-observatory (candidate) | **No — deferred** |

4.6a and 4.6b are deferred out of this increment, the same way 1.4 and 3.5 were deferred out of 2.1/2.3: both are unvalidated tool candidates in `docs/toolchain.md` ("not smoke-tested"), and 4.6b specifically needs a live running server — a materially different precondition class from every static/checkout-based criterion built so far (same class as the Playwright/Lighthouse gap noted elsewhere). They will land in their own later increment alongside 1.4/3.5.

**Also explicitly out of scope:** the P1/P2 critical-penalty capping rules (`quality-framework.md`§3.2), even though both are keyed directly on this increment's own tools (Gitleaks for P1, Trivy/pip-audit/`pnpm audit`/`composer audit` for P2). That capping logic lives in `score_repository`'s category-aggregation layer — a separate track (the scoring/report pipeline's "scope C", not yet started; scope A merged 2026-09-23). This increment only produces `Finding`/`Score` rows at `ScoreLevel.CRITERION`, exactly like categories 1-3; it does not touch `score_repository`'s aggregation code.

Seven `ToolRunner`s total: `PipAuditRunner`, `PnpmAuditRunner`, `ComposerAuditRunner` (4.1); `GitleaksRunner` (4.2); `SemgrepRunner` (4.3); `TrivyImageRunner` (4.4); `HadolintRunner` (4.5).

## 2. Goal

Repeat the normalization pattern established in 2.1-2.3 (raw `ToolResult` -> `Finding`/`Score` at criterion level) for category 4. No infrastructure changes are needed to the `ToolRunner` protocol, orchestrator, or data model. This is the first increment whose runners shell out to `docker run` directly (Gitleaks, Trivy image scan, Hadolint all lack a native/`uvx`/`npx` wrapper, per `toolchain.md`) — a small shared helper is introduced for that, not a protocol change.

## 3. Resolved design decisions

Four points left ambiguous or underspecified by `quality-framework.md`§4.4 were resolved during design:

**3.1 — Severity-tiered scoring bands for 4.1/4.3/4.4.** The catalog says "severity-tiered" but gives no numeric bands (unlike 1.1's explicit cycle-count table). Resolved: a 4-level band keyed on the *worst severity present*, same shape as 1.1's cycle-count bands:

| Worst severity present | Score |
|---|---|
| none | 10 |
| LOW / MEDIUM | 6 |
| HIGH | 4 |
| CRITICAL | 2 |

Severity source per criterion:
- **4.1**: the CVE's own native severity (already CVSS-tiered by pip-audit/`pnpm audit`/`composer audit`).
- **4.3**: Semgrep's own three-level severity, mapped `ERROR`->HIGH, `WARNING`->MEDIUM, `INFO`->LOW. Semgrep has no native CRITICAL tier in its default/auto config (no custom rule metadata is special-cased in this increment), so a 4.3 `Score` never actually lands on the CRITICAL band in practice — the band table stays uniform across 4.1/4.3/4.4 for consistency and future-proofing rather than hand-tuning a 3-level table for this one criterion.
- **4.4**: Trivy is invoked with `--severity HIGH,CRITICAL` (per `toolchain.md`, already filtering out LOW/MEDIUM/UNKNOWN at the tool level), so only the HIGH/CRITICAL rows of the table are ever reachable for this criterion.

**3.2 — Secrets scoring (4.2), no severity gradient.** Gitleaks findings don't carry a severity tier the way CVE/SAST tools do. Resolved: a 3-level band keyed on the frozen pre-filter rule already validated at the Phase 3 pilots (`quality-framework.md`§3.2, test-fixture and `.env.*.example` patterns):

| State | Score |
|---|---|
| no hits | 10 |
| hits, but all match the pre-filter (probable false positive) | 8 |
| >=1 hit does not match the pre-filter | 2 |

A pre-filtered hit is still recorded as a `Finding` (never silently dropped — the pre-filter narrows what counts as "confirmed" for the *score*, it doesn't change Gitleaks' own raw evidence, same principle stated in `quality-framework.md`§3.2), but with `confidence=LOW` instead of `HIGH`. No new `FindingStatus`/`HumanVerdict` enum value is introduced — `human_verdict` stays at its default `UNREVIEWED`, since distinguishing "confirmed" for the P1 penalty is deferred along with the rest of critical-penalty logic (see §1).

Pre-filter rule (ported as-is from `quality-framework.md`§3.2, both pilot-calibration passes):
- a `generic-api-key`-class hit in a `tests?/`/`test_*` path, on a variable matching `fake_*`/`mock_*`/`dummy_*`, **or**
- a hit whose file path matches `.env.*.example` / `.env.*.template` / `.env.*.sample`.

**3.3 — Dockerfile hardening (4.5) formula.** The catalog says "Hadolint findings density" (archetype B) but doesn't define the ratio. Resolved: reuse the exact archetype-B pattern already established by `normalize_lint_pass_rate` (covered/applicable), applied per-Dockerfile rather than per-file-line: `score = (dockerfiles with zero Hadolint findings / total dockerfiles scanned) × 10`. Consistent with treating "clean" as the unit, same as lint pass rate treating a clean *file* as the unit.

**3.4 — Dockerfile/image discovery.** Reuses the discovery rule already validated and written up in `toolchain.md`'s Containers section: exclude `vendor/`, `node_modules/`, and any `.git`-worktree-style nested directory when walking for Dockerfiles (the exact pitfall found on Summit-Stats — 9 Dockerfiles found naively, most of them vendored/duplicated noise). `TrivyImageRunner` does not build images itself; it only scans an image already present from the target repo's own prior local Docker usage (same precondition documented in `toolchain.md`: "the audit system does not build images itself as a side effect of scanning").

## 4. Runners — 4.1 Dependency vulnerabilities (CVE)

**`PipAuditRunner`** (`scope="subproject"`, `supported_stacks={"python"}`, `tool_name="pip-audit"`)
Invocation: `uvx --python /usr/bin/python3.13 pip-audit -r requirements.txt --format json` — the `--python` workaround is required (per `toolchain.md`: `uv`-managed Python builds ship without `ensurepip`, breaking pip-audit's internal ephemeral venv creation otherwise). `N/A` (no `Finding`/`Score`) if the sub-project has no `requirements.txt`/`pyproject.toml` dependency manifest.

**`PnpmAuditRunner`** (`scope="subproject"`, `supported_stacks={"javascript"}`, `tool_name="pnpm-audit"`)
Invocation: native `pnpm audit --json` (already-present pnpm, per `toolchain.md`).

**`ComposerAuditRunner`** (`scope="subproject"`, `supported_stacks={"php"}`, `tool_name="composer-audit"`)
Invocation: native `composer audit --format=json` (already-present composer, per `toolchain.md`).

All three: `raw_output` shape `{"vulnerabilities": [{"id": str, "package": str, "severity": str, "fix_available": bool}, ...]}`, normalized to a common severity vocabulary (`CRITICAL`/`HIGH`/`MEDIUM`/`LOW`) in the runner itself, since each tool's raw JSON uses its own severity spelling (pip-audit has no native severity field at all — resolved by mapping via the advisory's CVSS score if present, else `MEDIUM` as a conservative default, documented inline as provisional).

## 5. Runner — 4.2 Secrets in tracked history

**`GitleaksRunner`** (`scope="repo"`, `supported_stacks=frozenset()`, `tool_name="gitleaks"`)
Invocation: `docker run --rm -v <repo>:/repo zricethezav/gitleaks git /repo --report-format json --report-path /repo/.gitleaks-report.json --exit-code 0` (git-history mode, default — never `--no-git`, per the config decision in `toolchain.md`). `--exit-code 0` forces a clean exit regardless of findings, since findings are read from the report file, not inferred from exit code. `raw_output`: `{"findings": [{"rule": str, "file": str, "line": int, "match": str, "commit": str}, ...]}`.

## 6. Runner — 4.3 SAST findings

**`SemgrepRunner`** (`scope="repo"`, `supported_stacks=frozenset()`, `tool_name="semgrep"`)
Invocation: `uvx semgrep --config auto --json` (default/auto ruleset — not the `p/security-audit` registry ruleset, which is reserved for the deferred 4.6a). `raw_output`: `{"results": [{"check_id": str, "path": str, "start": {"line": int}, "extra": {"severity": str, "message": str}}, ...]}`.

## 7. Runner — 4.4 Container image vulnerabilities

**`TrivyImageRunner`** (`scope="repo"`, `supported_stacks=frozenset()`, `tool_name="trivy-image"`)
Invocation: `docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image --format json --severity HIGH,CRITICAL --scanners vuln <image>`. Image name resolution: read from a locally built image matching the repo's own naming convention (`docker compose config --images`, or a Dockerfile-adjacent image tag already present via `docker images`) — if none is found, the runner returns `raw_output={"image_found": false}` and the normalizer maps that to `None` (`N/A`), never triggering a build. `raw_output` (image found): `{"image_found": true, "image": str, "vulnerabilities": [{"id": str, "severity": str, "pkg": str, "fix_version": str | None}, ...]}`.

## 8. Runner — 4.5 Dockerfile hardening

**`HadolintRunner`** (`scope="repo"`, `supported_stacks=frozenset()`, `tool_name="hadolint"`)
Discovers Dockerfiles per §3.4's rule, then for each: `docker run --rm -i hadolint/hadolint hadolint --format json -` (stdin-piped). `raw_output`: `{"dockerfiles": [{"path": str, "findings": [{"code": str, "level": str, "message": str, "line": int}, ...]}, ...]}`.

## 9. Normalization — raw `ToolResult` -> `Finding`/`Score`

Same governing rules as 2.1-2.3 (`Score` rows at `ScoreLevel.CRITERION` only; missing-data -> no `Finding`/no `Score`).

**4.1 — Findings and Score.** One `Finding` per vulnerability (`severity` = the runner-normalized tier, `confidence=HIGH` — deterministic tool output), `description` includes the CVE/advisory id and package name. Multi-sub-project/multi-tool aggregation: worst-severity-wins across every contributing sub-project and tool (a `backend/` Python sub-project's pip-audit result and a `frontend/` JS sub-project's `pnpm audit` result both feed the same criterion), same worst-band precedent as 1.1/2.3. `Score.value` from §3.1's band table.

**4.2 — Findings and Score.** One `Finding` per Gitleaks hit, `confidence` per §3.2's pre-filter rule, `file`/`line` from the hit's own location. `Score.value` from §3.2's 3-level table.

**4.3 — Findings and Score.** One `Finding` per Semgrep result (`severity` mapped per §3.1, `confidence=HIGH`), `file`/`line` from `path`/`start.line`. `Score.value` from §3.1's band table.

**4.4 — Findings and Score.** `None` (`N/A`) if `image_found` is `false`. Otherwise one `Finding` per vulnerability (`severity` HIGH or CRITICAL only, `confidence=HIGH`). `Score.value` from §3.1's band table (only its HIGH/CRITICAL rows reachable, per §3.1).

**4.5 — Score only, no per-finding Findings for the ratio itself; one Finding per Hadolint rule violation.** One `Finding` per Hadolint finding (`severity=LOW`, `confidence=HIGH` — deterministic linter output), `file`/`line` from the Dockerfile path/line. `Score.value` from §3.3's ratio formula. `None` (`N/A`) if zero Dockerfiles discovered.

All five normalizers attach to the same `ScoringRun` (`get_or_create_scoring_run`, unchanged since 2.1) for the current `Audit` + "Quality Framework v1.0" `MethodologyVersion`.

## 10. Error handling / edge cases

- **4.1**: no dependency manifest for a given stack in any sub-project -> `None` (`N/A`) for that stack's contribution; if *no* sub-project of any supported stack exists, the whole criterion is `None`.
- **4.2**: Gitleaks always runs (repo-scope, no stack precondition) — never `N/A`, absence of any hit is a real "clean" result (band 10).
- **4.3**: Semgrep always runs (repo-scope) — never `N/A`, same reasoning as 4.2.
- **4.4**: `N/A` whenever no locally built image is found — this is expected to be the common case across most of the portfolio (most repos are not run via `docker compose` locally at audit time), not an error.
- **4.5**: `N/A` whenever zero Dockerfiles are discovered after applying the exclusion rule (§3.4) — expected for any repo with no containerization at all.
- Per-runner crash isolation is already guaranteed at the protocol level (`ToolRunner`, since 2.0) — one runner crashing (including a Docker-daemon-unavailable failure) does not affect any other runner in the same audit.
- Docker-daemon unavailability (Gitleaks/Trivy/Hadolint's shared precondition) is treated exactly like any other non-zero-exit tool failure — recorded as missing data, not defaulted to a score.

## 11. Testing

Same "zero mock" discipline as 2.1-2.3 — real subprocess/Docker invocations against synthetic `tmp_path` git fixtures (`init_git_repo`), no stubbed tool output. Docker-based runner tests require a local Docker daemon (same precondition already implicitly assumed by the project's dev/CI environment, per `toolchain.md`'s D7 ephemeral-Docker strategy).

- `PipAuditRunner`/`PnpmAuditRunner`/`ComposerAuditRunner` each need: one fixture with a known-vulnerable pinned dependency, one fixture with a clean lock/manifest, one fixture with no manifest at all (the 4.1 `N/A` case in §10).
- `GitleaksRunner` needs: a fixture with a real-looking committed secret, a fixture whose only hit matches the test-fixture/`.env.*.example` pre-filter (§3.2), and a clean fixture.
- `SemgrepRunner` needs: a fixture with at least one `ERROR`-severity finding, one `WARNING`-only fixture, and a clean fixture.
- `TrivyImageRunner` needs: a fixture where a matching local image exists (built ephemeral for the test) with at least one HIGH/CRITICAL CVE, and a fixture with `image_found=false` (§10).
- `HadolintRunner` needs: a Dockerfile with at least one finding, a clean Dockerfile, and a repo with no Dockerfile at all (the 4.5 `N/A` case), plus one fixture exercising the vendored/worktree-duplicate exclusion rule (§3.4), mirroring the regression already written up for Trivy/Vitest in `toolchain.md`.
- Normalization tests cover: worst-severity-wins aggregation across sub-projects (4.1), the pre-filter/confidence distinction (4.2), the ratio formula with a multi-Dockerfile fixture (4.5), and every `N/A` path in §10.
- Per this project's established lesson (2.2's Task 17, reinforced every increment since): **before considering this increment done, run a real `radar-audit run` against an actual portfolio repo** (GeoChallenge-Tracker, whose `backend/Dockerfile` already has documented Hadolint/Trivy smoke-test results in `toolchain.md`) and inspect the resulting `Score`/`Finding` rows for plausibility.

## 12. Out of scope for increment 2.4

- Criteria 4.6a (AuthN/authZ hygiene) and 4.6b (HTTP security headers) — deferred to their own later increment, same treatment as 1.4/3.5 (see §1).
- P1/P2 critical-penalty capping (`quality-framework.md`§3.2), even though both are grounded in this increment's own tools — deferred to the scoring pipeline's "scope C" (category/global-level aggregation), a separate track (see §1).
- `CATEGORY`/`GLOBAL` level `Score` rows, N/A weight-redistribution — still deferred to the same later dedicated aggregation work noted in every prior category's spec.
- Recalibrating the §3 severity-tier bands against real portfolio data — deferred to Phase 5's full-portfolio run, same caveat as every prior increment's provisional thresholds.
- Non-Docker-daemon environments (e.g. rootless/Podman-only hosts) — the project's existing Docker-based tools (actionlint's original candidate, D7) already assume a standard Docker daemon; no new assumption introduced here.

---

## 13. Global constraints for the implementation plan

- No `ToolRunner` protocol changes, no orchestrator changes, no new Alembic migration — 2.1 already built every structural piece this increment needs.
- A small shared helper for constructing/running a `docker run ...` subprocess command is introduced (used by `GitleaksRunner`, `TrivyImageRunner`, `HadolintRunner`) to avoid triplicating the same subprocess-invocation boilerplate — not a `ToolRunner` protocol change, just an internal implementation detail shared across three runner files.
- Gitleaks must always run in git-history mode (default), never `--no-git`, per the config decision already validated in `toolchain.md`.
- `TrivyImageRunner` never builds an image as a side effect of scanning — `N/A` if none is found locally already.
- `Score` rows this increment writes are `ScoreLevel.CRITERION` only — no `CATEGORY`/`GLOBAL` row is ever created here.
- The numeric bands introduced in §3 must be marked in code comments/docstrings as resolved-but-provisional (agreed during design, not yet calibrated against real portfolio data), same discipline as every prior increment's thresholds.
- Tests use real subprocess/Docker invocations against `tmp_path` git fixtures — no mocking of subprocess or tool output.
- Before the increment is marked done, a real `radar-audit run` against GeoChallenge-Tracker must be performed and its output inspected for plausibility, per §11's closing note.
