"""V10 scripted external MCP client proof (roadmap 04, PR-V4 evidence).

Spawns the PRODUCTION entrypoint ``python -m verity.mcp`` as a real stdio
subprocess (the way an external Cline client would), drives all four frozen
tools, records the trace, then kills the server, restarts a fresh one on
the same database and proves the cited IDs resolve to identical canonical
payloads - the roadmap V10 restart proof, automated and CI-reproducible to
complement the recorded Cline Desktop session. Skips until the real
``verity.service`` exists.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("verity.service") is None,
    reason="verity.service (PR-A4) not merged yet; V10 requires the real service",
)

from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import get_default_environment, stdio_client  # noqa: E402
from verity.config import load_config  # noqa: E402
from verity.models import IngestMode, IngestRequest  # noqa: E402
from verity.service import build_service  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).parent / "fixtures" / "contracts_v1"
FOUR_TOOLS = {"search_evidence", "get_requirement", "get_evidence", "check_coverage"}

REFUND_CODE = "def accept_refund(purchase, now):\n    return (now - purchase.date).days <= 30\n"
REFUND_TEST = (
    "import sys\nfrom pathlib import Path\n"
    "sys.path.insert(0, str(Path(__file__).resolve().parent.parent))\n"
    "from src.refund import accept_refund\n\n\n"
    "def test_refund_within_window():\n"
    "    assert accept_refund(purchase, now)\n"
)


@pytest.fixture()
def demo_env(tmp_path: Path) -> dict:
    """A demo workspace + config + seeded DB, exactly like the runbook."""

    workspace = tmp_path / "demo-workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "tests").mkdir(parents=True)
    (workspace / "src" / "refund.py").write_text(REFUND_CODE, encoding="utf-8")
    (workspace / "tests" / "test_refund.py").write_text(REFUND_TEST, encoding="utf-8")
    data = tmp_path / "data"
    documents = tmp_path / "documents"
    data.mkdir()
    documents.mkdir()
    toml = tmp_path / "verity.toml"
    toml.write_text(
        "config_version = \"1.0.0\"\n"
        f"database_path = \"{(data / 'verity.sqlite3').as_posix()}\"\n"
        f"data_dir = \"{data.as_posix()}\"\n"
        f"source_root = \"{documents.as_posix()}\"\n\n"
        "[workspaces.demo]\n"
        f"root = \"{workspace.as_posix()}\"\n"
        "test_command = [\"python\", \"-m\", \"pytest\", \"-q\"]\n",
        encoding="utf-8",
    )
    config = load_config(path=str(toml))
    service = build_service(config=config)
    result = asyncio.run(
        service.ingest(
            IngestRequest(source_path="payments.md", mode=IngestMode.AUTO),
            (FIXTURES / "payments.md").read_bytes(),
        )
    )
    assert result.created_new_version is True
    return {**get_default_environment(), "VERITY_CONFIG_PATH": str(toml)}


def _server_params(env: dict) -> StdioServerParameters:
    return StdioServerParameters(command=sys.executable, args=["-m", "verity.mcp"], cwd=str(ROOT), env=env)


async def _session_flow(env: dict, restart_check: dict | None) -> dict:
    trace: dict = {}
    async with stdio_client(_server_params(env)) as (read, write):
        async with ClientSession(read, write) as client:
            init = await client.initialize()
            trace["server"] = f"{init.server_info.name} {init.server_info.version}"
            tools = await client.list_tools()
            trace["tools"] = sorted(t.name for t in tools.tools)
            assert set(trace["tools"]) == FOUR_TOOLS

            search = await client.call_tool("search_evidence", {"query": "refund window"})
            payload = search.structured_content
            trace["search_total"] = payload["total_returned"]
            trace["retrieval_mode"] = payload["retrieval_mode"]
            top = payload["items"][0]
            trace["evidence_id"] = top["evidence_id"]
            trace["requirement_id"] = top["requirement_id"]
            trace["citation"] = top["citation"]["label"]
            trace["quote"] = top["quote"]

            requirement = await client.call_tool(
                "get_requirement", {"requirement_id": trace["requirement_id"]}
            )
            trace["requirement_local_id"] = requirement.structured_content["local_id"]

            evidence = await client.call_tool("get_evidence", {"evidence_id": trace["evidence_id"]})
            trace["evidence_payload"] = evidence.structured_content

            coverage = await client.call_tool(
                "check_coverage",
                {"requirement_ids": [trace["requirement_id"]], "workspace_id": "demo"},
            )
            trace["coverage_id"] = coverage.structured_content["coverage_id"]
            trace["coverage_status"] = coverage.structured_content["results"][0]["status"]

            if restart_check is not None:
                after = await client.call_tool(
                    "get_evidence", {"evidence_id": restart_check["evidence_id"]}
                )
                assert after.structured_content == restart_check["evidence_payload"]
                trace["restart_resolved"] = True
    return trace


def test_v10_external_client_trace_and_restart(demo_env):
    first = asyncio.run(_session_flow(demo_env, None))
    print("\n=== V10 external client trace (server #1) ===")
    print(json.dumps({k: v for k, v in first.items() if k != "evidence_payload"}, indent=2))
    assert first["search_total"] >= 1
    assert first["citation"].strip()
    assert first["evidence_id"].startswith("ev_")
    assert first["requirement_id"].startswith("req_")
    assert first["evidence_payload"]["evidence"]["score"] is None

    # Restart proof: a brand-new server process on the same database must
    # resolve the same cited evidence identically.
    second = asyncio.run(_session_flow(demo_env, first))
    assert second["restart_resolved"] is True
    assert second["evidence_id"] == first["evidence_id"]
    print("=== V10 restart proof: cited IDs resolve identically on server #2 ===")