"""Minimal hand-built PDF generator for VERITY test fixtures (Piyush-owned).

Produces simple, valid PDF 1.4 files with uncompressed content streams so the
fixture provenance is fully inspectable. Used to create:

* ``payments.pdf``  — two text pages, known passage on page 2.
* ``image_only.pdf`` — one page containing an image XObject and NO text
  operators, so text extraction finds no usable page (no OCR is attempted).

This module is fixture tooling only; it is never imported by ``verity``.
"""

from __future__ import annotations


def _literal(text: str) -> str:
    out = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    return "(" + out + ")"


def _content_stream(lines: list[str]) -> bytes:
    parts = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            parts.append("0 -16 Td")
        parts.append(_literal(line) + " Tj")
    parts.append("ET")
    return "\n".join(parts).encode("latin-1")


def _image_stream() -> bytes:
    # One single-byte grayscale pixel.
    return b"\x80"


def build_text_pdf(pages: list[list[str]]) -> bytes:
    """Return PDF bytes with one page per entry; each page shows its lines."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    font_id = add(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    )
    page_ids: list[int] = []
    content_ids: list[int] = []
    for lines in pages:
        stream = _content_stream(lines)
        content_ids.append(
            add(
                b"<< /Length %d >>\nstream\n" % len(stream)
                + stream
                + b"\nendstream"
            )
        )
    pages_obj_index = len(objects) + len(pages) + 1
    for content_id in content_ids:
        page_ids.append(
            add(
                (
                    "<< /Type /Page /Parent %d 0 R /MediaBox [0 0 612 792] "
                    "/Resources << /Font << /F1 %d 0 R >> >> "
                    "/Contents %d 0 R >>" % (pages_obj_index, font_id, content_id)
                ).encode("latin-1")
            )
        )
    kids = " ".join("%d 0 R" % pid for pid in page_ids)
    pages_id = add(
        ("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, len(page_ids))).encode(
            "latin-1"
        )
    )
    assert pages_id == pages_obj_index
    catalog_id = add(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    return _assemble(objects, catalog_id)


def build_image_only_pdf() -> bytes:
    """One page with an image XObject and no text operators at all."""
    objects: list[bytes] = []
    image = _image_stream()
    image_id = len(objects) + 1
    objects.append(
        b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 "
        b"/ColorSpace /DeviceGray /BitsPerComponent 8 /Length %d >>\nstream\n"
        % len(image)
        + image
        + b"\nendstream"
    )
    content = b"q 200 0 0 200 72 500 cm /Im1 Do Q"
    content_id = len(objects) + 1
    objects.append(
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream"
    )
    page_id = len(objects) + 1
    objects.append(
        (
            "<< /Type /Page /Parent 4 0 R /MediaBox [0 0 612 792] "
            "/Resources << /XObject << /Im1 %d 0 R >> >> "
            "/Contents %d 0 R >>" % (image_id, content_id)
        ).encode("latin-1")
    )
    pages_id = len(objects) + 1
    objects.append(b"<< /Type /Pages /Kids [%d 0 R] /Count 1 >>" % page_id)
    catalog_id = len(objects) + 1
    objects.append(b"<< /Type /Catalog /Pages %d 0 R >>" % pages_id)
    return _assemble(objects, catalog_id)


def _assemble(objects: list[bytes], catalog_id: int) -> bytes:
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % index + body + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += b"%010d 00000 n \n" % off
    out += (
        b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, catalog_id, xref_at)
    )
    return bytes(out)