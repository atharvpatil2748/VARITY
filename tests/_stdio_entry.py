"""Subprocess entry for stdio transport tests (roadmap V2-V4).

Serves the four real MCP tools over FakeVerityService on stdio so tests can
spawn a child process exactly the way an external Cline client would. Never
used by the production entrypoint (python -m verity.mcp), which refuses to
run without the real VerityService (no silent mock substitution).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
for _p in (str(ROOT), str(TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fakes.fake_verity_service import FakeVerityService  # noqa: E402
from verity.mcp.server import main  # noqa: E402

_REQUIRED_FIXTURES = (
    "search_result",
    "search_result_empty",
    "requirement",
    "evidence_lookup",
    "coverage_result",
)


def _load_fixtures() -> dict:
    fixture_dir = TESTS_DIR / "fixtures" / "v1"
    return {
        stem: json.loads((fixture_dir / f"{stem}.json").read_text(encoding="utf-8"))
        for stem in _REQUIRED_FIXTURES
    }


if __name__ == "__main__":
    main(service=FakeVerityService(_load_fixtures()))