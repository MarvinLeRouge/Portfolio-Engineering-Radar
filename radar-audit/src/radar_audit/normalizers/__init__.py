from __future__ import annotations

from collections.abc import Callable

from radar_core.models.audit import ToolResult
from radar_core.models.methodology import Criterion
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session

from radar_audit.normalizers.ci_test_execution import normalize_ci_test_execution
from radar_audit.normalizers.code_duplication import normalize_code_duplication
from radar_audit.normalizers.complexity_hotspots import normalize_complexity_hotspots
from radar_audit.normalizers.container_image_vulnerabilities import (
    normalize_container_image_vulnerabilities,
)
from radar_audit.normalizers.cyclomatic_complexity import normalize_cyclomatic_complexity
from radar_audit.normalizers.dead_code import normalize_dead_code
from radar_audit.normalizers.dependency_circularity import normalize_dependency_circularity
from radar_audit.normalizers.dependency_vulnerabilities import (
    normalize_dependency_vulnerabilities,
)
from radar_audit.normalizers.design_doc import normalize_design_doc
from radar_audit.normalizers.dockerfile_hardening import normalize_dockerfile_hardening
from radar_audit.normalizers.docstring_coverage import normalize_docstring_coverage
from radar_audit.normalizers.e2e_tests import normalize_e2e_tests
from radar_audit.normalizers.integration_tests import normalize_integration_tests
from radar_audit.normalizers.lint_pass_rate import normalize_lint_pass_rate
from radar_audit.normalizers.module_size import normalize_module_size
from radar_audit.normalizers.precommit_gate import normalize_precommit_gate
from radar_audit.normalizers.sast_findings import normalize_sast_findings
from radar_audit.normalizers.secrets_in_history import normalize_secrets_in_history
from radar_audit.normalizers.type_check_pass_rate import normalize_type_check_pass_rate
from radar_audit.normalizers.unit_test_pass_rate import normalize_unit_test_pass_rate

NormalizerFn = Callable[[Session, ScoringRun, Criterion, list[ToolResult]], Score | None]

CRITERION_NORMALIZERS: dict[tuple[str, str], NormalizerFn] = {
    (
        "Architecture & design",
        "Dependency direction / circularity",
    ): normalize_dependency_circularity,
    ("Architecture & design", "Architectural documentation present"): normalize_design_doc,
    ("Architecture & design", "Module size distribution"): normalize_module_size,
    ("Code quality", "Linter clean pass rate"): normalize_lint_pass_rate,
    ("Code quality", "Type-checking pass"): normalize_type_check_pass_rate,
    ("Code quality", "Cyclomatic complexity"): normalize_cyclomatic_complexity,
    ("Code quality", "Pre-commit quality gate"): normalize_precommit_gate,
    ("Code quality", "Code duplication"): normalize_code_duplication,
    ("Maintainability", "Complexity hotspots"): normalize_complexity_hotspots,
    ("Maintainability", "Dead code / unused exports"): normalize_dead_code,
    (
        "Maintainability",
        "Documentation-in-code (docstring/comment coverage)",
    ): normalize_docstring_coverage,
    (
        "Testing & reliability",
        "Unit tests present & passing, with coverage",
    ): normalize_unit_test_pass_rate,
    ("Testing & reliability", "Integration tests"): normalize_integration_tests,
    ("Testing & reliability", "E2E tests"): normalize_e2e_tests,
    ("Testing & reliability", "CI executes the test suite"): normalize_ci_test_execution,
    ("Security", "Dependency vulnerabilities (CVE)"): normalize_dependency_vulnerabilities,
    ("Security", "Secrets in tracked history"): normalize_secrets_in_history,
    ("Security", "SAST findings"): normalize_sast_findings,
    ("Security", "Container image vulnerabilities"): normalize_container_image_vulnerabilities,
    ("Security", "Dockerfile hardening"): normalize_dockerfile_hardening,
}
