"""N5: allowlisted test runner (contract 12/14, owner Vanashree).

Tests are never run by an arbitrary MCP-supplied command. ``run_tests=true``
invokes only the preconfigured allowlisted ``test_command`` for the
configured workspace, with a 20-second timeout and no network expectation.
Output is bounded and captured as evidence only when it can be mapped to
a test file/line present in the snapshot; otherwise it is reported as a
limitation and never treated as proof for an unrelated requirement.
"""

from __future__ import annotations

import re
import subprocess

from ..config import WorkspaceConfig
from ..errors import VerityError
from ..models import EvidenceBasis, TestEvidence, TestOutcome
from .workspace import WorkspaceSnapshot

#: Contract 12: allowlisted test command timeout.
TEST_TIMEOUT_SECONDS = 20
#: Bounded captured output per run.
MAX_OUTPUT_CHARS = 2000

#: Output mapping: `path:line` or `path` mentions of snapshot test files.
_LOCATION_RE = re.compile(
    r"(?P<path>[\w./\\-]+\.(?:py|js|ts|jsx|tsx|go|rs)):(?P<line>\d+)"
)
_PATH_MENTION_RE = re.compile(r"(?P<path>[\w./\\-]+\.(?:py|js|ts|jsx|tsx|go|rs))")


class AllowlistedTestRunner:
    """Runs the configured allowlisted test command once per coverage run."""

    def __init__(self, workspace: WorkspaceConfig) -> None:
        self._workspace = workspace

    async def run(self, snapshot: WorkspaceSnapshot) -> tuple[TestEvidence, ...]:
        """Execute the allowlisted command and return mapped outcomes.

        Raises ``COVERAGE_UNAVAILABLE`` when no allowlisted command is
        configured; the coverage service records that as a limitation and
        leaves retrieved tests at ``not_run`` (never ``IMPLEMENTED``).
        """
        command = tuple(self._workspace.test_command)
        if not command:
            raise VerityError(
                "COVERAGE_UNAVAILABLE",
                "no allowlisted test command configured for this workspace",
                {"workspace_id": snapshot.workspace_id},
            )
        try:
            completed = subprocess.run(
                list(command),
                cwd=snapshot.root,
                capture_output=True,
                text=True,
                timeout=TEST_TIMEOUT_SECONDS,
            )
            outcome = (
                TestOutcome.PASSED if completed.returncode == 0 else TestOutcome.FAILED
            )
            output = (completed.stdout + "\n" + completed.stderr)[
                -MAX_OUTPUT_CHARS:
            ]
        except subprocess.TimeoutExpired:
            raise VerityError(
                "TIMEOUT",
                f"allowlisted test command exceeded {TEST_TIMEOUT_SECONDS}s",
                {"workspace_id": snapshot.workspace_id},
            ) from None
        except OSError as exc:
            raise VerityError(
                "COVERAGE_UNAVAILABLE",
                "allowlisted test command could not be executed",
                {"workspace_id": snapshot.workspace_id},
            ) from exc

        return self._map_outcomes(snapshot, outcome, output)

    def _map_outcomes(
        self,
        snapshot: WorkspaceSnapshot,
        outcome: TestOutcome,
        output: str,
    ) -> tuple[TestEvidence, ...]:
        """Map bounded output to snapshot test files only (contract 12)."""
        members = {f.relative_path for f in snapshot.files}
        test_paths = {
            path for path in members
            if "test" in path.replace("\\", "/").lower()
            or path.replace("\\", "/").rsplit("/", 1)[-1].startswith("check_")
        }
        mapped: dict[str, TestEvidence] = {}
        for match in _LOCATION_RE.finditer(output):
            path = match.group("path").replace("\\", "/")
            resolved = next(
                (member for member in members
                 if member == path or member.endswith("/" + path)
                 or member.rsplit("/", 1)[-1] == path.rsplit("/", 1)[-1]),
                None,
            )
            if resolved is None or resolved not in test_paths:
                continue
            if resolved not in mapped:
                mapped[resolved] = TestEvidence(
                    path=resolved,
                    start_line=int(match.group("line")),
                    end_line=int(match.group("line")),
                    excerpt=output[-500:],
                    basis=EvidenceBasis.TEST_EXECUTION,
                    outcome=outcome,
                )
        if not mapped:
            for match in _PATH_MENTION_RE.finditer(output):
                path = match.group("path").replace("\\", "/")
                resolved = next(
                    (member for member in test_paths
                     if member.rsplit("/", 1)[-1] == path.rsplit("/", 1)[-1]),
                    None,
                )
                if resolved is not None and resolved not in mapped:
                    mapped[resolved] = TestEvidence(
                        path=resolved,
                        start_line=1,
                        end_line=1,
                        excerpt=output[-500:],
                        basis=EvidenceBasis.TEST_EXECUTION,
                        outcome=outcome,
                    )
        return tuple(mapped.values())