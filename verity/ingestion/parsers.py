"""General document parsers (contract 05, owner Piyush).

Formats (MVP): PDF (``application/pdf``), Markdown (``text/markdown``),
TXT (``text/plain``) and code ``.py``/``.js``/``.ts``/``.tsx``/``.java``
(``text/x-code``). Unsupported types return ``UNSUPPORTED_FORMAT``.

Guarantees (contract 05 / P3 acceptance):

* ``ParsedBlock`` ordinals are contiguous from zero.
* Page/line information is never invented: Markdown/TXT/code blocks have
  ``page=null`` and exact 1-based source line spans; PDF blocks carry the
  known ``page`` (>=1) and ``start_line/end_line=null`` because extracted
  PDF text lines are not verified against the source representation
  (contract 03). Character offsets are ``null`` (not verified).
* A scanned/image-only PDF page is a warning (partial extraction); when no
  page yields usable text the parse fails with ``PARSER_ERROR``. No OCR is
  attempted or claimed.
* Empty bytes, invalid UTF-8 text and corrupt PDFs fail with ``PARSER_ERROR``.

Output is one canonical ``ParsedDocument`` JSON instance (dict) validating
against ``Docs/contracts/21_VERITY_V1_JSON_SCHEMAS.json`` $defs.
"""

from __future__ import annotations

import os
import re
import zlib

from verity.errors import VerityError
from .spec import SpecParser, looks_like_spec

PARSER_VERSION = "1.0.0"

_MD_EXTENSIONS = {".md", ".markdown"}
_TXT_EXTENSIONS = {".txt", ".text"}
_CODE_EXTENSIONS = {".py", ".js", ".ts", ".tsx", ".java"}
_PDF_EXTENSIONS = {".pdf"}

_HEADING_RE = re.compile(r"^(#{1,6}) (\S.*)$")
_FENCE_RE = re.compile(r"^```")


def _parser_error(message: str, filename: str) -> VerityError:
    return VerityError("PARSER_ERROR", message, {"file": filename, "line": None})


def _decode_text(data: bytes, filename: str) -> str:
    if not data:
        raise _parser_error("document has no content", filename)
    try:
        text = data.decode("utf-8")  # strict
    except UnicodeDecodeError as exc:
        raise _parser_error("document is not valid UTF-8", filename) from exc
    if not text.strip():
        raise _parser_error("document has no usable content", filename)
    return text


def _metadata(parser_name: str, title: str | None, warnings: list[str],
              page_count: int | None = None) -> dict:
    return {
        "metadata_version": "1.0.0",
        "title": title,
        "source_key": None,
        "project": None,
        "spec_version": None,
        "language": None,
        "page_count": page_count,
        "parser_name": parser_name,
        "parser_version": PARSER_VERSION,
        "warnings": warnings,
    }


class _BlockBuilder:
    def __init__(self) -> None:
        self.blocks: list[dict] = []

    def add(self, text: str, block_type: str, page: int | None,
            heading_path: list[str], start_line: int | None,
            end_line: int | None) -> None:
        self.blocks.append({
            "ordinal": len(self.blocks),
            "text": text,
            "block_type": block_type,
            "page": page,
            "heading_path": list(heading_path),
            "start_line": start_line,
            "end_line": end_line,
            "start_offset": None,
            "end_offset": None,
        })


def _group_paragraphs(lines: list[str], base_line: int | None, page: int | None,
                      heading_path: list[str], builder: _BlockBuilder,
                      block_type: str = "paragraph") -> None:
    """Group consecutive nonblank lines into one block each."""
    pending: list[str] = []
    first = last = 0
    for index, line in enumerate(lines):
        if not line.strip():
            if pending:
                builder.add("\n".join(pending), block_type, page, heading_path,
                            None if base_line is None else base_line + first,
                            None if base_line is None else base_line + last)
                pending = []
            continue
        if not pending:
            first = index
        last = index
        pending.append(line)
    if pending:
        builder.add("\n".join(pending), block_type, page, heading_path,
                    None if base_line is None else base_line + first,
                    None if base_line is None else base_line + last)


class MarkdownParser:
    """Heading-aware Markdown parser for general documents (not specs)."""

    def parse(self, data: bytes, filename: str, media_type: str) -> dict:
        text = _decode_text(data, filename)
        lines = text.splitlines()
        builder = _BlockBuilder()
        stack: list[tuple[int, str]] = []
        title: str | None = None
        in_fence = False
        fence_start = 0
        fence_lines: list[str] = []
        para: list[str] = []
        para_first = 0

        def flush_paragraph() -> None:
            nonlocal para, para_first
            if para:
                path = [name for _, name in stack]
                builder.add("\n".join(para), "paragraph", None, path,
                            para_first, para_first + len(para) - 1)
                para = []

        for index, line in enumerate(lines):
            no = index + 1
            if _FENCE_RE.match(line):
                if in_fence:
                    fence_lines.append(line)
                    path = [name for _, name in stack]
                    builder.add("\n".join(fence_lines), "code", None, path,
                                fence_start, no)
                    fence_lines = []
                    in_fence = False
                else:
                    flush_paragraph()
                    in_fence = True
                    fence_start = no
                    fence_lines = [line]
                continue
            if in_fence:
                fence_lines.append(line)
                continue
            match = _HEADING_RE.match(line)
            if match:
                flush_paragraph()
                level, heading = len(match.group(1)), match.group(2).strip()
                while stack and stack[-1][0] >= level:
                    stack.pop()
                stack.append((level, heading))
                path = [name for _, name in stack]
                builder.add(heading, "heading", None, path, no, no)
                if title is None and level == 1:
                    title = heading
                continue
            if not line.strip():
                flush_paragraph()
                continue
            if line.startswith("- "):
                flush_paragraph()
                path = [name for _, name in stack]
                builder.add(line[2:].strip(), "paragraph", None, path, no, no)
                continue
            if not para:
                para_first = no
            para.append(line)
        if in_fence:
            raise _parser_error("unterminated fenced code block", filename)
        flush_paragraph()
        if not builder.blocks:
            raise _parser_error("document has no usable content", filename)
        return {
            "metadata": _metadata("markdown", title, []),
            "blocks": builder.blocks,
            "media_type": media_type,
            "kind": "general",
            "spec_requirements": [],
            "spec_entities": [],
        }


class TextParser:
    """Paragraph parser for plain text (blank-line separated)."""

    def parse(self, data: bytes, filename: str, media_type: str) -> dict:
        text = _decode_text(data, filename)
        builder = _BlockBuilder()
        _group_paragraphs(text.splitlines(), 1, None, [], builder)
        if not builder.blocks:
            raise _parser_error("document has no usable content", filename)
        return {
            "metadata": _metadata("text", None, []),
            "blocks": builder.blocks,
            "media_type": media_type,
            "kind": "general",
            "spec_requirements": [],
            "spec_entities": [],
        }


class CodeParser:
    """Code parser: code blocks with exact file line positions."""

    def parse(self, data: bytes, filename: str, media_type: str) -> dict:
        text = _decode_text(data, filename)
        builder = _BlockBuilder()
        _group_paragraphs(text.splitlines(), 1, None, [], builder, block_type="code")
        if not builder.blocks:
            raise _parser_error("document has no usable content", filename)
        return {
            "metadata": _metadata("code", None, []),
            "blocks": builder.blocks,
            "media_type": media_type,
            "kind": "general",
            "spec_requirements": [],
            "spec_entities": [],
        }


def _extract_text(content: bytes) -> list[str]:
    """Extract text lines from a PDF content stream (Tj/TJ/quotes, Td/T*/Tm breaks)."""
    text = content.decode("latin-1", errors="replace")
    lines: list[str] = []
    current: list[str] = []

    def newline() -> None:
        if current:
            lines.append("".join(current).strip())
            current.clear()

    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "(":
            j = i + 1
            depth = 1
            buf: list[str] = []
            while j < n and depth:
                c = text[j]
                if c == "\\" and j + 1 < n:
                    buf.append(c)
                    buf.append(text[j + 1])
                    j += 2
                    continue
                if c == "(":
                    depth += 1
                elif c == ")":
                    depth -= 1
                    if depth == 0:
                        break
                buf.append(c)
                j += 1
            current.append(_decode_pdf_string("(" + "".join(buf) + ")"))
            i = j + 1
            continue
        if ch == "<" and (i + 1 >= n or text[i + 1] != "<"):
            j = text.find(">", i)
            if j == -1:
                break
            current.append(_decode_pdf_string(text[i:j + 1]))
            i = j + 1
            continue
        if ch.isalpha() or ch == "*":
            j = i
            while j < n and (text[j].isalpha() or text[j] == "*"):
                j += 1
            op = text[i:j]
            if op in ("Td", "TD", "T*", "Tm", "BT", "ET"):
                newline()
            i = j
            continue
        i += 1
    newline()
    return lines


class PdfParser:
    """Per-page PDF text parser (contract 05). No OCR: image-only pages warn."""

    def parse(self, data: bytes, filename: str, media_type: str) -> dict:
        if not data:
            raise _parser_error("PDF has no content", filename)
        if not data.startswith(b"%PDF-"):
            raise _parser_error("not a PDF file (missing %PDF- header)", filename)
        objects = {int(m.group(1)): m.group(3) for m in _OBJ_RE.finditer(data)}
        if not objects:
            raise _parser_error("PDF contains no objects", filename)
        page_bodies = self._page_order(objects)
        if not page_bodies:
            raise _parser_error("PDF contains no page objects", filename)

        builder = _BlockBuilder()
        warnings: list[str] = []
        usable = 0
        for page_no, body in enumerate(page_bodies, start=1):
            content = self._page_content(body, objects)
            if content is None:
                warnings.append(
                    f"page {page_no}: content stream uses an unsupported "
                    "filter; no text extracted and no OCR performed"
                )
                continue
            lines = _extract_text(content)
            if not any(line.strip() for line in lines):
                warnings.append(
                    f"page {page_no}: no extractable text (image-only or "
                    "empty page); no OCR performed"
                )
                continue
            usable += 1
            _group_paragraphs(lines, None, page_no, [], builder)
        if usable == 0:
            raise _parser_error(
                "PDF has no usable text pages (image-only extraction is "
                "unsupported; no OCR performed)",
                filename,
            )
        return {
            "metadata": _metadata("pdf_text", None, warnings,
                                  page_count=len(page_bodies)),
            "blocks": builder.blocks,
            "media_type": media_type,
            "kind": "general",
            "spec_requirements": [],
            "spec_entities": [],
        }

    @staticmethod
    def _page_order(objects: dict[int, bytes]) -> list[bytes]:
        def flatten(ref: int, out: list[bytes], depth: int = 0) -> None:
            body = objects.get(ref)
            if body is None or depth > 16:
                return
            if re.search(rb"/Type\s*/Page\b", body):
                out.append(body)
                return
            kids = _KIDS_RE.search(body)
            if kids:
                for kid in _REF_RE.finditer(kids.group(1)):
                    flatten(int(kid.group(1)), out, depth + 1)

        ordered: list[bytes] = []
        for body in objects.values():
            if re.search(rb"/Type\s*/Catalog\b", body):
                pages = _REF_RE.search(body)
                if pages:
                    flatten(int(pages.group(1)), ordered)
                break
        if not ordered:
            for number in sorted(objects):
                body = objects[number]
                if re.search(rb"/Type\s*/Page\b", body):
                    ordered.append(body)
        return ordered

    @staticmethod
    def _page_content(page_body: bytes, objects: dict[int, bytes]) -> bytes | None:
        refs: list[int] = []
        single = _CONTENTS_RE.search(page_body)
        if single:
            refs.append(int(single.group(1)))
        else:
            arr = _CONTENTS_ARR_RE.search(page_body)
            if arr:
                refs.extend(int(m.group(1)) for m in _REF_RE.finditer(arr.group(1)))
        chunks: list[bytes] = []
        for ref in refs:
            body = objects.get(ref)
            if body is None:
                continue
            match = _STREAM_RE.search(body)
            if not match:
                continue
            header = body[: match.start()]
            if b"/FlateDecode" in header:
                try:
                    chunks.append(zlib.decompress(match.group(1)))
                except zlib.error:
                    return None
            elif b"/Filter" in header:
                return None
            else:
                chunks.append(match.group(1))
        return b"\n".join(chunks) if chunks else b""


# PDF stream/object helpers (resolved at call time).
_OBJ_RE = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)endobj", re.DOTALL)
_STREAM_RE = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.DOTALL)
_KIDS_RE = re.compile(rb"/Kids\s*\[([^\]]*)\]")
_REF_RE = re.compile(rb"(\d+)\s+\d+\s+R")
_CONTENTS_RE = re.compile(rb"/Contents\s+(\d+)\s+\d+\s+R")
_CONTENTS_ARR_RE = re.compile(rb"/Contents\s*\[([^\]]*)\]")
_TOKEN_RE = re.compile(
    r"\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]*>|\bTd\b|\bTD\b|\bT\*|\bTm\b|\bTj\b|\bTJ\b|\bBT\b|\bET\b"
)


def _decode_pdf_string(token: str) -> str:
    if token.startswith("<"):
        hex_digits = re.sub(r"\s", "", token[1:-1])
        if len(hex_digits) % 2:
            hex_digits += "0"
        try:
            return bytes.fromhex(hex_digits).decode("latin-1")
        except ValueError:
            return ""
    body = token[1:-1]
    out: list[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            mapped = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f",
                      "(": "(", ")": ")", "\\": "\\", "'": "'"}.get(nxt)
            if mapped is not None:
                out.append(mapped)
                i += 2
                continue
            if nxt.isdigit():
                octal = ""
                while i + 1 < len(body) and body[i + 1].isdigit() and len(octal) < 3:
                    octal += body[i + 1]
                    i += 1
                out.append(chr(int(octal, 8) % 256))
                i += 1
                continue
            out.append(nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


class ParserRouter:
    """Contract-16 ``Parser``: route bytes to the right format parser (contract 05)."""

    def __init__(self) -> None:
        self._markdown = MarkdownParser()
        self._text = TextParser()
        self._code = CodeParser()
        self._pdf = PdfParser()
        self._spec = SpecParser()

    def parse(self, data: bytes, filename: str, media_type: str) -> dict:
        kind = resolve_kind(media_type, filename)
        if kind is None:
            raise VerityError(
                "UNSUPPORTED_FORMAT",
                f"unsupported document type: media_type={media_type!r} "
                f"file={filename!r}",
                {"file": filename, "media_type": media_type},
            )
        if kind == "markdown":
            if looks_like_spec(data):
                # Contract 05: malformed front matter beginning verity_spec is
                # a spec error, never silently general.
                return self._spec.parse(data, filename, media_type)
            return self._markdown.parse(data, filename, media_type)
        if kind == "text":
            return self._text.parse(data, filename, media_type)
        if kind == "code":
            return self._code.parse(data, filename, media_type)
        return self._pdf.parse(data, filename, media_type)


def resolve_kind(media_type: str, filename: str) -> str | None:
    """Map media type (preferred) or file extension to a parser kind."""
    declared = (media_type or "").split(";")[0].strip().lower()
    by_media = {
        "text/markdown": "markdown",
        "text/plain": "text",
        "application/pdf": "pdf",
        "text/x-code": "code",
    }
    if declared in by_media:
        return by_media[declared]
    if declared and declared not in ("application/octet-stream", "binary/octet-stream"):
        return None  # explicitly known-unsupported media type
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in _MD_EXTENSIONS:
        return "markdown"
    if ext in _TXT_EXTENSIONS:
        return "text"
    if ext in _CODE_EXTENSIONS:
        return "code"
    if ext in _PDF_EXTENSIONS:
        return "pdf"
    return None