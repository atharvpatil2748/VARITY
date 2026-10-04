"""Strict VERITY Spec Markdown 1.0.0 parser (contract 04, owner Piyush).

Implements the exact authored format of
``Docs/contracts/04_VERITY_SPEC_SCHEMA.md``:

* YAML front matter with required ``verity_spec: "1.0.0"``, ``source_key``,
  ``project``, ``title``, ``spec_version`` and optional ``authors`` /
  ``language``. Unknown keys are rejected. ``verity_spec`` mismatch is
  ``VERSION_UNSUPPORTED``; every other authored-shape problem is
  ``SPEC_VALIDATION_ERROR`` with the offending 1-based source line.
* Exact heading grammar: ``# Requirements`` (required) with ``## REQ-###: Title``
  sections, then optional ``# API definitions``, ``# Acceptance criteria``,
  ``# References`` in that order. Requirement children ``### Constraints``,
  ``### Edge cases``, ``### References`` in that order, each at most once.
* Duplicate or dangling ``REQ-*``/``API-*``/``AC-*`` identifiers reject the
  full ingestion. No partial structured spec commit. The parser never
  generates IDs or infers relationships.

The parser emits one canonical ``ParsedDocument`` JSON instance (dict)
validating against ``Docs/contracts/21_VERITY_V1_JSON_SCHEMAS.json``
$defs/ParsedDocument, ParsedBlock, SpecRequirementDraft, SpecEntityDraft.
Blocks carry exact 1-based source line spans and ``page=null`` (Markdown).
All line numbers refer to the original UTF-8 Markdown line count from 1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from verity.errors import VerityError

SPEC_PARSER_NAME = "verity_spec"
SPEC_PARSER_VERSION = "1.0.0"
SPEC_FORMAT_VERSION = "1.0.0"

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_HEADING_RE = re.compile(r"^(#{1,6}) (\S.*)$")
_REQ_ID_RE = re.compile(r"^REQ-[0-9]{3,}$")
_API_ID_RE = re.compile(r"^API-[0-9]{3,}$")
_AC_ID_RE = re.compile(r"^AC-[0-9]{3,}$")
_ANY_LOCAL_ID_RE = re.compile(r"^(REQ|API|AC)-[0-9]{3,}$")
_AC_REFERENCES_RE = re.compile(r"^References: *REQ-[0-9]{3,}( *, *REQ-[0-9]{3,})*$")
_FRONT_KEY_RE = re.compile(r"^([a-z][a-z0-9_]*):(.*)$")

_REQUIRED_FRONT_KEYS = ("verity_spec", "source_key", "project", "title", "spec_version")
_OPTIONAL_FRONT_KEYS = ("authors", "language")

_SECTION_ORDER = ("Requirements", "API definitions", "Acceptance criteria", "References")
_REQ_SUBSECTIONS = ("Constraints", "Edge cases", "References")


def _spec_error(
    message: str, line: int, filename: str, code: str = "SPEC_VALIDATION_ERROR"
) -> VerityError:
    return VerityError(code, message, {"file": filename, "line": line})


@dataclass
class _Block:
    ordinal: int
    text: str
    block_type: str
    start_line: int
    end_line: int
    heading_path: list[str]

    def to_json(self) -> dict:
        return {
            "ordinal": self.ordinal,
            "text": self.text,
            "block_type": self.block_type,
            "page": None,
            "heading_path": list(self.heading_path),
            "start_line": self.start_line,
            "end_line": self.end_line,
            "start_offset": None,
            "end_offset": None,
        }


@dataclass
class _ParserState:
    """Line cursor over a list of source lines."""

    lines: list[str]
    pos: int = 0

    def peek(self) -> str | None:
        return self.lines[self.pos] if self.pos < len(self.lines) else None

    def next(self) -> str | None:
        value = self.peek()
        if value is not None:
            self.pos += 1
        return value

    def eof(self) -> bool:
        return self.pos >= len(self.lines)


@dataclass
class _FrontMatter:
    values: dict[str, object]
    end_line: int  # 1-based line number of the closing '---'


def _unquote(value: str, line: int, filename: str) -> str:
    value = value.strip()
    for quote in ('"', "'"):
        if value.startswith(quote):
            if not value.endswith(quote) or len(value) < 2:
                raise _spec_error(f"malformed quoted value: {value!r}", line, filename)
            return value[1:-1]
    return value


def _parse_inline_list(value: str, line: int, filename: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        raise _spec_error(f"authors must be an inline list, got {value!r}", line, filename)
    inner = value[1:-1].strip()
    if not inner:
        return []
    items: list[str] = []
    for raw in inner.split(","):
        item = _unquote(raw, line, filename)
        if not item:
            raise _spec_error("authors entries must be nonempty", line, filename)
        items.append(item)
    return items


def parse_front_matter(lines: list[str], filename: str) -> _FrontMatter:
    """Parse strict YAML front matter; ``lines`` is the whole file's lines."""
    if not lines or lines[0].strip() != "---":
        raise _spec_error("spec file must start with YAML front matter ('---')", 1, filename)
    values: dict[str, object] = {}
    close = None
    for index in range(1, len(lines)):
        line = lines[index]
        if line.strip() == "---":
            close = index
            break
        if not line.strip():
            raise _spec_error("blank line inside front matter", index + 1, filename)
        match = _FRONT_KEY_RE.match(line)
        if not match:
            raise _spec_error(f"malformed front matter line: {line!r}", index + 1, filename)
        key, raw_value = match.group(1), match.group(2)
        if key in values:
            raise _spec_error(f"duplicate front matter key: {key}", index + 1, filename)
        if key not in _REQUIRED_FRONT_KEYS and key not in _OPTIONAL_FRONT_KEYS:
            raise _spec_error(f"unknown front matter key: {key}", index + 1, filename)
        if key == "authors":
            values[key] = _parse_inline_list(raw_value, index + 1, filename)
        else:
            values[key] = _unquote(raw_value, index + 1, filename)
    if close is None:
        raise _spec_error("front matter is not closed with '---'", len(lines), filename)

    if "verity_spec" not in values:
        raise _spec_error("front matter is missing verity_spec", 2, filename)
    if values["verity_spec"] != SPEC_FORMAT_VERSION:
        raise _spec_error(
            f"unsupported verity_spec {values['verity_spec']!r}; "
            f"expected {SPEC_FORMAT_VERSION!r}",
            2,
            filename,
            code="VERSION_UNSUPPORTED",
        )
    for key in _REQUIRED_FRONT_KEYS:
        if key == "verity_spec":
            continue
        if key not in values or not str(values[key]):
            raise _spec_error(f"front matter is missing {key}", 2, filename)
    if not _SLUG_RE.fullmatch(str(values["source_key"])):
        raise _spec_error("source_key must match the slug syntax of contract 03", 2, filename)
    if "language" in values and not str(values["language"]):
        raise _spec_error("language must be a nonempty BCP 47 tag when present", 2, filename)
    return _FrontMatter(values=values, end_line=close + 1)


class _BodyParser:
    """Parses the Markdown body into blocks and validated section records."""

    def __init__(self, lines: list[str], body_start_line: int, filename: str) -> None:
        self.state = _ParserState(lines=lines)
        self.filename = filename
        self.body_start_line = body_start_line  # 1-based line number of lines[0]
        self.blocks: list[_Block] = []
        self.requirements: list[dict] = []
        self.entities: list[dict] = []
        self._seen: dict[str, dict[str, int]] = {"REQ": {}, "API": {}, "AC": {}}
        self._pending_refs: list[tuple[str, int]] = []

    def _line_no(self, index: int) -> int:
        return self.body_start_line + index

    def _add_block(self, text: str, block_type: str, start_line: int,
                   end_line: int, path: list[str]) -> int:
        ordinal = len(self.blocks)
        self.blocks.append(
            _Block(ordinal=ordinal, text=text, block_type=block_type,
                   start_line=start_line, end_line=end_line, heading_path=list(path))
        )
        return ordinal

    def _register(self, namespace: str, local_id: str, line: int) -> None:
        if local_id in self._seen[namespace]:
            first = self._seen[namespace][local_id]
            raise _spec_error(
                f"duplicate {namespace} identifier {local_id} "
                f"(first defined at line {first})",
                line,
                self.filename,
            )
        self._seen[namespace][local_id] = line

    def parse(self) -> None:
        # Split the body into top-level sections at level-1 headings.
        sections: list[tuple[str, int, int]] = []  # (name, heading_index, end_index)
        current: tuple[str, int, int] | None = None
        for index, line in enumerate(self.state.lines):
            match = _HEADING_RE.match(line)
            if match and len(match.group(1)) == 1:
                title = match.group(2).strip()
                if title not in _SECTION_ORDER:
                    raise _spec_error(
                        f"unrecognized top-level section {title!r}",
                        self._line_no(index), self.filename,
                    )
                if current is not None:
                    sections.append((current[0], current[1], index - 1))
                current = (title, index, index)
            elif match and current is None:
                raise _spec_error(
                    "heading before the first top-level section",
                    self._line_no(index), self.filename,
                )
            elif line.strip() and current is None:
                raise _spec_error(
                    "body content outside any top-level section",
                    self._line_no(index), self.filename,
                )
        if current is not None:
            sections.append((current[0], current[1], len(self.state.lines) - 1))
        if not sections:
            raise _spec_error(
                "spec body is empty; expected '# Requirements'",
                self.body_start_line, self.filename,
            )

        order_index = -1
        seen: set[str] = set()
        for name, heading_index, _ in sections:
            if name in seen:
                raise _spec_error(
                    f"duplicate top-level section {name!r}",
                    self._line_no(heading_index), self.filename,
                )
            seen.add(name)
            new_index = _SECTION_ORDER.index(name)
            if new_index <= order_index:
                raise _spec_error(
                    f"top-level section {name!r} is out of order",
                    self._line_no(heading_index), self.filename,
                )
            order_index = new_index
        if sections[0][0] != "Requirements":
            raise _spec_error(
                "missing required '# Requirements' section: it must come first",
                self._line_no(sections[0][1]), self.filename,
            )

        handlers = {
            "Requirements": self._parse_requirements,
            "API definitions": self._parse_api,
            "Acceptance criteria": self._parse_acceptance,
            "References": self._parse_references,
        }
        for name, start_index, end_index in sections:
            body = self.state.lines[start_index + 1: end_index + 1]
            handlers[name](body, self._line_no(start_index + 1), [name])

        for local_id, line in self._pending_refs:
            namespace = local_id.split("-", 1)[0]
            if local_id not in self._seen[namespace]:
                raise _spec_error(
                    f"dangling reference to unknown {namespace} identifier {local_id}",
                    line, self.filename,
                )


    def _parse_requirements(self, body: list[str], body_start_line: int, path: list[str]) -> None:
        cursor = _ParserState(lines=body)
        self._add_block(path[0], "heading", body_start_line - 1, body_start_line - 1, path)
        current: dict | None = None
        req_path: list[str] = []
        subsection: str | None = None
        seen_subsections: list[str] = []
        normative: list[str] = []
        pending: list[str] = []
        pending_first = pending_last = 0

        def flush() -> None:
            nonlocal pending, pending_first, pending_last
            if pending:
                block_path = req_path if subsection is None else req_path + [subsection]
                self._add_block("\n".join(pending), "paragraph",
                                pending_first, pending_last, block_path)
                if subsection is None:
                    normative.append("\n".join(pending))
                pending = []
                pending_first = pending_last = 0

        def close_requirement() -> None:
            nonlocal current, normative, subsection, seen_subsections
            if current is None:
                return
            flush()
            if not normative:
                raise _spec_error(
                    f"{current['local_id']} must begin with at least one "
                    "nonempty normative paragraph",
                    current["_line"], self.filename,
                )
            current["text"] = "\n".join(normative)
            current["block_end"] = len(self.blocks) - 1
            self.requirements.append({
                "local_id": current["local_id"],
                "title": current["title"],
                "text": current["text"],
                "constraints": current["constraints"],
                "edge_cases": current["edge_cases"],
                "api_refs": current["api_refs"],
                "reference_ids": current["reference_ids"],
                "acceptance_local_ids": current["acceptance_local_ids"],
                "block_start": current["block_start"],
                "block_end": current["block_end"],
            })
            current = None
            normative = []
            subsection = None
            seen_subsections = []

        while True:
            line = cursor.peek()
            if line is None:
                break
            cursor.next()
            no = body_start_line + cursor.pos - 1
            if not line.strip():
                flush()
                continue
            match = _HEADING_RE.match(line)
            if match:
                flush()
                level, title = len(match.group(1)), match.group(2).strip()
                if level == 2:
                    close_requirement()
                    id_part, sep, title_part = title.partition(": ")
                    if not (sep and _REQ_ID_RE.fullmatch(id_part) and title_part):
                        raise _spec_error(
                            f"malformed requirement heading {line!r}; "
                            "expected '## REQ-###: Title'",
                            no, self.filename,
                        )
                    self._register("REQ", id_part, no)
                    req_path = path + [title]
                    block_start = self._add_block(title, "heading", no, no, req_path)
                    current = {
                        "local_id": id_part,
                        "title": title_part,
                    "path_title": title,
                        "constraints": [],
                        "edge_cases": [],
                        "api_refs": [],
                        "reference_ids": [],
                        "acceptance_local_ids": [],
                        "block_start": block_start,
                        "block_end": block_start,
                        "_line": no,
                    }
                    normative = []
                    subsection = None
                    seen_subsections = []
                    continue
                if level == 3:
                    if current is None:
                        raise _spec_error(
                            f"subsection {title!r} outside a requirement section",
                            no, self.filename,
                        )
                    if title not in _REQ_SUBSECTIONS:
                        raise _spec_error(
                            f"unrecognized structured child heading {title!r}",
                            no, self.filename,
                        )
                    if title in seen_subsections:
                        raise _spec_error(f"duplicate '### {title}' subsection", no, self.filename)
                    if seen_subsections and _REQ_SUBSECTIONS.index(title) <= _REQ_SUBSECTIONS.index(seen_subsections[-1]):
                        raise _spec_error(
                            f"'### {title}' is out of order "
                            "(expected order: Constraints, Edge cases, References)",
                            no, self.filename,
                        )
                    seen_subsections.append(title)
                    subsection = title
                    self._add_block(title, "heading", no, no, req_path + [title])
                    continue
                raise _spec_error(
                    f"heading depth {level} is invalid inside '# Requirements'",
                    no, self.filename,
                )
            if line.startswith("- ") or (line[:1].isspace() and line.lstrip().startswith("- ")):
                flush()
                if subsection is None:
                    raise _spec_error(
                        "bullets are only valid under Constraints, Edge cases "
                        "or References",
                        no, self.filename,
                    )
                cursor.pos -= 1  # let the bullet helper consume this line
                self._parse_requirement_bullets(cursor, body_start_line, req_path, subsection, current)
                continue
            if current is None:
                raise _spec_error(
                    "content before the first '## REQ-###: Title' heading",
                    no, self.filename,
                )
            if pending_first == 0:
                pending_first = no
            pending_last = no
            pending.append(line)
        close_requirement()
        if not self.requirements:
            raise _spec_error(
                "'# Requirements' must contain at least one '## REQ-###: Title' section",
                body_start_line - 1, self.filename,
            )

    def _parse_requirement_bullets(self, cursor: _ParserState, line_base: int,
                                   req_path: list[str],
                                   subsection: str, current: dict) -> None:
        """Collect first-level '- ' bullets into the current requirement."""
        while True:
            line = cursor.peek()
            if line is None or not line.strip() or _HEADING_RE.match(line):
                return
            no = line_base + cursor.pos
            if line.startswith("- "):
                cursor.next()
                content = line[2:].strip()
                if not content:
                    raise _spec_error("bullet must have nonempty text", no, self.filename)
                self._add_block(content, "paragraph", no, no, req_path + [subsection])
                if subsection == "Constraints":
                    current["constraints"].append(content)
                elif subsection == "Edge cases":
                    current["edge_cases"].append(content)
                else:
                    if not _ANY_LOCAL_ID_RE.fullmatch(content):
                        raise _spec_error(
                            f"reference bullet must be a local REQ/API/AC id, "
                            f"got {content!r}",
                            no, self.filename,
                        )
                    self._pending_refs.append((content, no))
                    if _API_ID_RE.fullmatch(content):
                        current["api_refs"].append(content)
                    else:
                        current["reference_ids"].append(content)
                        if _AC_ID_RE.fullmatch(content):
                            current["acceptance_local_ids"].append(content)
                continue
            if line[:1].isspace() and line.lstrip().startswith("- "):
                raise _spec_error(
                    "nested bullets are invalid in spec sections", no, self.filename
                )
            raise _spec_error(
                f"unexpected content {line!r} in {subsection}: only '- ' "
                "bullets are allowed",
                no, self.filename,
            )

    def _parse_api(self, body: list[str], body_start_line: int, path: list[str]) -> None:
        cursor = _ParserState(lines=body)
        self._add_block(path[0], "heading", body_start_line - 1, body_start_line - 1, path)
        current: dict | None = None
        pending: list[str] = []
        pending_first = pending_last = 0

        def flush() -> None:
            nonlocal pending, pending_first, pending_last
            if pending and current is not None:
                self._add_block("\n".join(pending), "paragraph",
                                pending_first, pending_last, path + [current["path_title"]])
                current["text_parts"].append("\n".join(pending))
                pending = []
                pending_first = pending_last = 0

        def close_entity() -> None:
            nonlocal current
            if current is None:
                return
            if not current["text_parts"]:
                raise _spec_error(
                    f"{current['local_id']} must have nonempty text",
                    current["_line"], self.filename,
                )
            self.entities.append({
                "kind": "api_definition",
                "local_id": current["local_id"],
                "title": current["title"],
                "text": "\n".join(current["text_parts"]),
                "reference_ids": [],
                "block_start": current["block_start"],
                "block_end": len(self.blocks) - 1,
            })
            current = None

        while True:
            line = cursor.peek()
            if line is None:
                break
            cursor.next()
            no = body_start_line + cursor.pos - 1
            if not line.strip():
                continue
            match = _HEADING_RE.match(line)
            if match:
                flush()
                level, title = len(match.group(1)), match.group(2).strip()
                if level != 2:
                    raise _spec_error(
                        "API definitions use only '## API-###: Title' headings",
                        no, self.filename,
                    )
                close_entity()
                id_part, sep, title_part = title.partition(": ")
                if not (sep and _API_ID_RE.fullmatch(id_part) and title_part):
                    raise _spec_error(
                        f"malformed API heading {line!r}; "
                        "expected '## API-###: Title'",
                        no, self.filename,
                    )
                self._register("API", id_part, no)
                block_start = self._add_block(title, "heading", no, no, path + [title])
                current = {
                    "local_id": id_part,
                    "title": title_part,
                    "path_title": title,
                    "text_parts": [],
                    "block_start": block_start,
                    "_line": no,
                }
                continue
            if line.startswith("- ") or (line[:1].isspace() and line.lstrip().startswith("- ")):
                raise _spec_error("bullets are invalid in API definitions", no, self.filename)
            if current is None:
                raise _spec_error(
                    "content before the first API definition heading", no, self.filename
                )
            if pending_first == 0:
                pending_first = no
            pending_last = no
            pending.append(line)
        flush()
        close_entity()

    def _parse_acceptance(self, body: list[str], body_start_line: int, path: list[str]) -> None:
        cursor = _ParserState(lines=body)
        self._add_block(path[0], "heading", body_start_line - 1, body_start_line - 1, path)
        current: dict | None = None
        pending: list[str] = []
        pending_first = pending_last = 0

        def flush() -> None:
            nonlocal pending, pending_first, pending_last
            if pending and current is not None:
                self._add_block("\n".join(pending), "paragraph",
                                pending_first, pending_last, path + [current["path_title"]])
                current["text_parts"].append("\n".join(pending))
                pending = []
                pending_first = pending_last = 0

        def close_entity() -> None:
            nonlocal current
            if current is None:
                return
            if not current["text_parts"]:
                raise _spec_error(
                    f"{current['local_id']} must have nonempty text",
                    current["_line"], self.filename,
                )
            if not current["reference_ids"]:
                raise _spec_error(
                    f"{current['local_id']} must end with a 'References: REQ-...' line",
                    current["_line"], self.filename,
                )
            self.entities.append({
                "kind": "acceptance_criterion",
                "local_id": current["local_id"],
                "title": current["title"],
                "text": "\n".join(current["text_parts"]),
                "reference_ids": current["reference_ids"],
                "block_start": current["block_start"],
                "block_end": len(self.blocks) - 1,
            })
            current = None

        while True:
            line = cursor.peek()
            if line is None:
                break
            cursor.next()
            no = body_start_line + cursor.pos - 1
            if not line.strip():
                continue
            match = _HEADING_RE.match(line)
            if match:
                flush()
                level, title = len(match.group(1)), match.group(2).strip()
                if level != 2:
                    raise _spec_error(
                        "acceptance criteria use only '## AC-###: Title' headings",
                        no, self.filename,
                    )
                close_entity()
                id_part, sep, title_part = title.partition(": ")
                if not (sep and _AC_ID_RE.fullmatch(id_part) and title_part):
                    raise _spec_error(
                        f"malformed acceptance heading {line!r}; "
                        "expected '## AC-###: Title'",
                        no, self.filename,
                    )
                self._register("AC", id_part, no)
                block_start = self._add_block(title, "heading", no, no, path + [title])
                current = {
                    "local_id": id_part,
                    "title": title_part,
                    "path_title": title,
                    "text_parts": [],
                    "reference_ids": [],
                    "references_line": None,
                    "block_start": block_start,
                    "_line": no,
                }
                continue
            if line.startswith("- ") or (line[:1].isspace() and line.lstrip().startswith("- ")):
                raise _spec_error("bullets are invalid in acceptance criteria", no, self.filename)
            if current is None:
                raise _spec_error(
                    "content before the first acceptance criterion heading",
                    no, self.filename,
                )
            stripped = line.strip()
            if stripped.startswith("References:"):
                if not _AC_REFERENCES_RE.match(stripped):
                    raise _spec_error(
                        f"malformed references line {line!r}; "
                        "expected 'References: REQ-001[, REQ-002]'",
                        no, self.filename,
                    )
                if current["references_line"] is not None:
                    raise _spec_error(
                        "duplicate References line in acceptance criterion",
                        no, self.filename,
                    )
                flush()
                refs = [part.strip() for part in stripped[len("References:"):].split(",")]
                current["reference_ids"] = refs
                current["references_line"] = no
                self._add_block(stripped, "paragraph", no, no, path + [current["path_title"]])
                for ref in refs:
                    self._pending_refs.append((ref, no))
                continue
            if current["references_line"] is not None:
                raise _spec_error(
                    "the References line must be the last line of an "
                    "acceptance criterion",
                    no, self.filename,
                )
            if pending_first == 0:
                pending_first = no
            pending_last = no
            pending.append(line)
        flush()
        close_entity()

    def _parse_references(self, body: list[str], body_start_line: int, path: list[str]) -> None:
        """Top-level '# References' yields general blocks, never requirements."""
        self._add_block(path[0], "heading", body_start_line - 1, body_start_line - 1, path)
        pending: list[str] = []
        pending_first = pending_last = 0

        def flush() -> None:
            nonlocal pending, pending_first, pending_last
            if pending:
                self._add_block("\n".join(pending), "paragraph",
                                pending_first, pending_last, path)
                pending = []
                pending_first = pending_last = 0

        for index, line in enumerate(body):
            no = body_start_line + index
            if _HEADING_RE.match(line):
                raise _spec_error(
                    "headings are not allowed inside top-level '# References'",
                    no, self.filename,
                )
            if not line.strip():
                flush()
                continue
            if pending_first == 0:
                pending_first = no
            pending_last = no
            pending.append(line)
        flush()


class SpecParser:
    """Strict parser for authored v1 spec documents (contract 04)."""

    def parse(self, data: bytes, filename: str, media_type: str) -> dict:
        try:
            text = data.decode("utf-8")  # strict
        except UnicodeDecodeError as exc:
            raise VerityError(
                "PARSER_ERROR", "spec document is not valid UTF-8",
                {"file": filename, "line": None},
            ) from exc
        if not text.strip():
            raise VerityError(
                "PARSER_ERROR", "spec document is empty",
                {"file": filename, "line": None},
            )
        lines = text.splitlines()
        front = parse_front_matter(lines, filename)
        body_lines = lines[front.end_line:]
        parser = _BodyParser(body_lines, front.end_line + 1, filename)
        parser.parse()
        metadata = {
            "metadata_version": "1.0.0",
            "title": front.values.get("title"),
            "source_key": front.values.get("source_key"),
            "project": front.values.get("project"),
            "spec_version": front.values.get("spec_version"),
            "language": front.values.get("language"),
            "page_count": None,
            "parser_name": SPEC_PARSER_NAME,
            "parser_version": SPEC_PARSER_VERSION,
            "warnings": [],
        }
        return {
            "metadata": metadata,
            "blocks": [block.to_json() for block in parser.blocks],
            "media_type": media_type,
            "kind": "spec",
            "spec_requirements": parser.requirements,
            "spec_entities": parser.entities,
        }


def looks_like_spec(data: bytes) -> bool:
    """True when the file begins with front matter whose first key is verity_spec.

    Used by the router's ``auto`` mode (contract 05): malformed front matter
    that begins ``verity_spec`` is a spec error, never silently general.
    """
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return False
    for line in lines[1:4]:
        if line.strip() == "---":
            return False
        if not line.strip():
            continue
        match = _FRONT_KEY_RE.match(line)
        return bool(match) and match.group(1) == "verity_spec"
    return False