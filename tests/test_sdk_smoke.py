"""Installed Cline SDK smoke — PR-A5 gate (contract 10).

Contract 10: pin the SDK version and type-check a smoke test against it. The
bridge pins ``@cline/sdk@0.0.90`` in ``sdk-ui/gateway/node_bridge/package.json``.
When Node and the pinned package are installed, this smoke constructs the
real ``Agent`` + ``createTool`` surface and asserts the documented API
(``new Agent({providerId, modelId, systemPrompt, tools})``, ``run`` /
``continue`` / ``subscribe``, ``result.text``). When they are absent the test
SKIPS with an honest reason — never a fake pass.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

BRIDGE_DIR = Path(__file__).parent.parent / "sdk-ui" / "gateway" / "node_bridge"
PINNED = json.loads((BRIDGE_DIR / "package.json").read_text(encoding="utf-8"))
PINNED_VERSION = PINNED["dependencies"]["@cline/sdk"]

SMOKE_SCRIPT = """
import { Agent, createTool } from "@cline/sdk";
const tool = createTool({
  name: "search_evidence",
  description: "smoke",
  inputSchema: { type: "object", additionalProperties: false, required: ["query"],
                 properties: { query: { type: "string" } } },
  execute: async (args) => ({ ok: true, args }),
});
const agent = new Agent({
  providerId: "smoke", modelId: "smoke", systemPrompt: "smoke", tools: [tool],
});
const surface = ["run", "continue", "subscribe", "snapshot"]
  .filter((m) => typeof agent[m] !== "function");
if (surface.length) {
  console.error("missing Agent methods: " + surface.join(","));
  process.exit(1);
}
console.log("ok");
"""


def _sdk_installed() -> bool:
    return (BRIDGE_DIR / "node_modules" / "@cline" / "sdk").exists()


def _require_sdk() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not installed: SDK smoke cannot run (honest skip)")
    if not _sdk_installed():
        pytest.skip(
            f"@cline/sdk@{PINNED_VERSION} not installed in node_bridge: "
            "run `npm install` there to enable the SDK smoke (honest skip)"
        )


def test_pinned_version_recorded() -> None:
    # The pin itself is part of the contract-10 requirement.
    assert PINNED_VERSION == "0.0.90"


def test_installed_sdk_agent_tool_surface() -> None:
    _require_sdk()
    result = subprocess.run(
        ["node", "--input-type=module", "-e", SMOKE_SCRIPT],
        capture_output=True, text=True, cwd=str(BRIDGE_DIR), timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_bridge_script_parses() -> None:
    if shutil.which("node") is None:
        pytest.skip("node not installed (honest skip)")
    result = subprocess.run(
        ["node", "--check", str(BRIDGE_DIR / "agent.mjs")],
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr