"""General parser contract tests (contract 05, P3 acceptance).

Covers: Markdown heading-aware blocks, TXT paragraphs, code line positions,
PDF per-page text with known page numbers, image-only PDF -> PARSER_ERROR,
partial extraction warning, invalid UTF-8 / empty bytes, UNSUPPORTED_FORMAT
and auto spec routing (malformed spec front matter is a spec error, never
silently general).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TESTS_DIR))

from support.pdf_builder import build_text_pdf

from verity.ingestion._compat import VerityError
from verity.ingestion.parsers import ParserRouter

FIXTURES = TESTS_DIR / "fixtures" / "contracts_v1"
router = ParserRouter()


def test_markdown_heading_aware_blocks() -> None:
    data = (FIXTURES / "architecture.md").read_bytes()
    doc = router.parse(data, "architecture.md", "text/markdown")
    assert doc["kind"] == "general"
    assert doc["metadata"]["title"] == "Payments architecture"
    headings = [b for b in doc["blocks"] if b["block_type"] == "heading"]
    assert [h["text"] for h in headings] == [
        "Payments architecture", "Overview", "Refund retry policy", "Storage",
    ]
    assert headings[1]["heading_path"] == ["Payments architecture", "Overview"]
    for block in doc["blocks"]:
        assert block["page"] is None
        assert block["start_line"] <= block["end_line"]


def test_markdown_paragraph_line_spans() -> None:
    data = (FIXTURES / "architecture.md").read_bytes()
    doc = router.parse(data, "architecture.md", "text/markdown")
    retry = next(
        b for b in doc["blocks"]
        if b["block_type"] == "paragraph" and "exponential backoff" in b["text"]
    )
    assert retry["start_line"] == 9
    assert retry["end_line"] == 12


def test_txt_paragraph_blocks() -> None:
    data = (FIXTURES / "security.txt").read_bytes()
    doc = router.parse(data, "security.txt", "text/plain")
    assert [b["block_type"] for b in doc["blocks"]] == ["paragraph"] * 3
    spans = [(b["start_line"], b["end_line"]) for b in doc["blocks"]]
    assert spans == [(1, 1), (3, 5), (7, 8)]
    assert "idempotency_key" in doc["blocks"][1]["text"]


def test_code_file_line_positions() -> None:
    code = (
        b"def refund(payment_id):\n"
        b"    return pay(payment_id)\n"
        b"\n"
        b"\n"
        b"def noop():\n"
        b"    pass\n"
    )
    doc = router.parse(code, "refund.py", "text/x-code")
    assert all(b["block_type"] == "code" for b in doc["blocks"])
    spans = [(b["start_line"], b["end_line"]) for b in doc["blocks"]]
    assert spans == [(1, 2), (5, 6)]
    for block in doc["blocks"]:
        assert block["page"] is None
        assert block["start_line"] is not None  # code must carry line positions


def test_pdf_two_pages_known_passage_on_page_2() -> None:
    data = (FIXTURES / "payments.pdf").read_bytes()
    doc = router.parse(data, "payments.pdf", "application/pdf")
    assert doc["metadata"]["page_count"] == 2
    pages = {b["page"] for b in doc["blocks"]}
    assert pages == {1, 2}
    for block in doc["blocks"]:
        assert block["start_line"] is None and block["end_line"] is None  # never invented
    page2 = [b for b in doc["blocks"] if b["page"] == 2]
    assert any(
        "Refunds are accepted only within 30 days of the original payment." in b["text"]
        for b in page2
    )
    assert doc["metadata"]["warnings"] == []


def test_image_only_pdf_is_parser_error() -> None:
    data = (FIXTURES / "image_only.pdf").read_bytes()
    with pytest.raises(VerityError) as excinfo:
        router.parse(data, "image_only.pdf", "application/pdf")
    assert excinfo.value.code == "PARSER_ERROR"
    assert "no usable text pages" in excinfo.value.message
    assert "no OCR" in excinfo.value.message


def test_partial_pdf_page_warns_but_parses() -> None:
    mixed = build_text_pdf([["Page one has text."], []])
    doc = router.parse(mixed, "mixed.pdf", "application/pdf")
    assert doc["metadata"]["page_count"] == 2
    assert [b["page"] for b in doc["blocks"]] == [1]
    assert len(doc["metadata"]["warnings"]) == 1
    assert "page 2" in doc["metadata"]["warnings"][0]
    assert "no OCR" in doc["metadata"]["warnings"][0]


def test_invalid_utf8_is_parser_error() -> None:
    with pytest.raises(VerityError) as excinfo:
        router.parse(b"\xff\xfe\x00bad", "bad.txt", "text/plain")
    assert excinfo.value.code == "PARSER_ERROR"


def test_empty_bytes_is_parser_error() -> None:
    with pytest.raises(VerityError) as excinfo:
        router.parse(b"", "empty.txt", "text/plain")
    assert excinfo.value.code == "PARSER_ERROR"


def test_unsupported_format() -> None:
    for name, media in [("page.html", "text/html"), ("book.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")]:
        with pytest.raises(VerityError) as excinfo:
            router.parse(b"data", name, media)
        assert excinfo.value.code == "UNSUPPORTED_FORMAT"


def test_spec_routed_automatically() -> None:
    data = (FIXTURES / "payments.md").read_bytes()
    doc = router.parse(data, "payments.md", "text/markdown")
    assert doc["kind"] == "spec"
    assert doc["metadata"]["parser_name"] == "verity_spec"
    assert len(doc["spec_requirements"]) == 3


def test_malformed_spec_front_matter_is_spec_error_never_general() -> None:
    bad = b'---\nverity_spec: "1.0.0"\nthis line is malformed\n---\n\n# Requirements\n'
    with pytest.raises(VerityError) as excinfo:
        router.parse(bad, "broken.md", "text/markdown")
    assert excinfo.value.code == "SPEC_VALIDATION_ERROR"