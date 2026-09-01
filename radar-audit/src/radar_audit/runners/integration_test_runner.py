from __future__ import annotations

import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput

_SKIP_DIRNAMES = {"node_modules", "vendor", ".venv", "dist", "build", "__pycache__"}


class IntegrationTestRunner:
    """Cross-stack filesystem heuristic classifying test files as integration or unit
    (criterion 3.2). No tool produces this signal directly -- see design spec §3.
    Runs once per repo (scope="repo"): a monorepo's Python/JS/PHP integration ratios
    are combined into one repo-wide figure.
    """

    tool_name = "integration-test-heuristic"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python", "javascript", "php"})
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 30

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        start = time.monotonic()

        files: list[dict[str, object]] = []
        for file_path in sorted(target_path.rglob("*")):
            if not file_path.is_file():
                continue
            if self._is_skipped(file_path, target_path, exclude_paths):
                continue
            classification = self._classify(file_path, target_path)
            if classification is None:
                continue
            files.append(
                {
                    "path": str(file_path.relative_to(target_path)),
                    "is_integration": classification,
                }
            )

        total = len(files)
        integration = sum(1 for f in files if f["is_integration"])

        duration_ms = int((time.monotonic() - start) * 1000)
        return RawToolOutput(
            command=f"integration-test-walk {target_path}",
            raw_output={
                "total_test_files": total,
                "integration_test_files": integration,
                "files": files,
            },
            exit_code=0,
            duration_ms=duration_ms,
        )

    def _classify(self, file_path: Path, target_path: Path) -> bool | None:
        parts = file_path.relative_to(target_path).parts
        name = file_path.name
        suffix = file_path.suffix

        if suffix == ".py":
            if not (name.startswith("test_") or name.endswith("_test.py")):
                return None
            if "integration" in parts:
                return True
            try:
                content = file_path.read_text(errors="ignore")
            except OSError:
                content = ""
            return "@pytest.mark.integration" in content

        if suffix in {".js", ".ts", ".jsx", ".tsx"}:
            stem = file_path.stem
            if ".test" not in stem and ".spec" not in stem:
                return None
            if "integration" in parts:
                return True
            return ".integration.test" in name or ".integration.spec" in name

        if suffix == ".php":
            if not name.endswith("Test.php"):
                return None
            if "tests" not in {p.lower() for p in parts}:
                return None
            return "Feature" in parts

        return None

    def _is_skipped(self, file_path: Path, target_path: Path, exclude_paths: list[Path]) -> bool:
        relative_parts = file_path.relative_to(target_path).parts
        if any(part in _SKIP_DIRNAMES for part in relative_parts):
            return True
        return any(
            excluded == file_path or excluded in file_path.parents for excluded in exclude_paths
        )
