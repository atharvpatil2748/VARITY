"""VERITY one-command launcher — seeds demo data and serves the API + UI.

Run from the repo root:
    py serve.py

Starts the REAL backend (VerityService) with the demo payments spec
ingested, serves the polished VERITY UI at http://localhost:8765, and
exposes the /api/v1 loopback API (contract 11) on the same port.

Open http://localhost:8765 for the default mock UI, or
http://localhost:8765/?api=real to use the live backend.
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SPEC = ROOT / "tests" / "fixtures" / "contracts_v1" / "payments.md"

REFUND_CODE = '''"""Refund handling (implements REQ-001 from the payments spec)."""


def accept_refund(purchase, now):
    """Refund window: accept only within 30 days (REQ-001)."""
    return (now - purchase.date).days <= 30
'''

REFUND_TEST = '''import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.refund import accept_refund


class Purchase:
    def __init__(self, date):
        self.date = date


def test_refund_within_window():
    from datetime import date, timedelta
    purchase = Purchase(date(2026, 10, 1))
    assert accept_refund(purchase, date(2026, 10, 31))
    assert not accept_refund(purchase, date(2026, 11, 1))
'''


def build_demo_app():
    """Build the real service + UI with demo data pre-seeded."""
    from fastapi import FastAPI
    from fastapi.responses import FileResponse
    from starlette.staticfiles import StaticFiles

    from verity.config import VerityConfig, WorkspaceConfig
    from verity.http import HealthState, create_app
    from verity.models import IngestMode, IngestRequest
    from verity.service import build_service

    tmp = Path(tempfile.mkdtemp(prefix="verity-demo-"))
    data_dir = tmp / "data"
    documents = tmp / "documents"
    workspace = tmp / "demo-workspace"
    data_dir.mkdir()
    documents.mkdir()

    # Seed demo workspace code
    src = workspace / "src" / "refund.py"
    test = workspace / "tests" / "test_refund.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    test.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(REFUND_CODE, encoding="utf-8")
    test.write_text(REFUND_TEST, encoding="utf-8")

    config = VerityConfig(
        data_dir=data_dir,
        source_root=documents,
        database_path=data_dir / "verity.sqlite3",
        workspaces={
            "demo": WorkspaceConfig(
                workspace_id="demo",
                root=workspace,
                test_command=(sys.executable, "-m", "pytest", "-q", "--tb=no"),
                exclude=(".git", ".venv", "node_modules", "dist"),
            )
        },
    )
    service = build_service(config=config)

    # Ingest demo documents
    asyncio.run(service.ingest(
        IngestRequest(source_path="payments.md", mode=IngestMode.SPEC),
        SPEC.read_bytes(),
    ))

    # Build FastAPI app: API routes first, then static UI
    app = create_app(service, HealthState(sdk_available=False))

    frontend = ROOT / "sdk-ui" / "frontend"
    app.mount("/", StaticFiles(directory=str(frontend), html=True), name="ui")

    return app


def main():
    try:
        import uvicorn
    except ImportError:
        sys.exit("uvicorn is required: pip install uvicorn")

    app = build_demo_app()
    print(
        "\n"
        "  ============================================\n"
        "  VERITY demo server\n"
        "  ============================================\n"
        "\n"
        "  UI (mock):      http://127.0.0.1:8765\n"
        "  UI (real API):  http://127.0.0.1:8765/?api=real\n"
        "  API health:     http://127.0.0.1:8765/api/v1/health\n"
        "\n"
        "  Ingested: payments.md (spec)\n"
        "  Workspace: demo-workspace/ with refund.py + tests\n"
        "  SDK chat: 503 SDK_UNAVAILABLE (honest - no gateway)\n"
        "  Coverage: check any REQ via the Coverage view\n"
        "\n"
        "  Ctrl+C to stop.\n"
    )
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


if __name__ == "__main__":
    main()