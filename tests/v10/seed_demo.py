"""Seed the demo for the V10 external-Cline session (roadmap 04, PR-V4).

Run from the repo root:  python tests/v10/seed_demo.py

Idempotent: creates the demo-workspace code/test files if absent (the
refund-window requirement REQ-001 implementation) and ingests the canonical
payments spec through the REAL service using the repo's verity.toml, so the
external Cline client's session cites real evidence. Prints the seeded
requirement/evidence IDs for the recording.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
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
    assert not accept_refund(purchase, date(2026, 10, 32))
'''


def seed_workspace() -> None:
    src = ROOT / "demo-workspace" / "src" / "refund.py"
    test = ROOT / "demo-workspace" / "tests" / "test_refund.py"
    src.parent.mkdir(parents=True, exist_ok=True)
    test.parent.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        src.write_text(REFUND_CODE, encoding="utf-8")
        print(f"created {src}")
    if not test.exists():
        test.write_text(REFUND_TEST, encoding="utf-8")
        print(f"created {test}")


def seed_corpus() -> None:
    from verity.config import load_config
    from verity.models import IngestMode, IngestRequest, SearchRequest
    from verity.service import build_service

    service = build_service(config=load_config())
    result = asyncio.run(
        service.ingest(
            IngestRequest(source_path="payments.md", mode=IngestMode.AUTO),
            SPEC.read_bytes(),
        )
    )
    print(f"ingested payments.md -> document {result.document.document_id} "
          f"(kind={result.document.kind.value}, created_new_version={result.created_new_version})")

    found = asyncio.run(service.search_evidence(SearchRequest(
        query="refund window", document_ids=None, document_kinds=None, chunk_kinds=None)))
    for item in found.items:
        print(f"  evidence {item.evidence_id}  citation: {item.citation.label}")


if __name__ == "__main__":
    seed_workspace()
    seed_corpus()