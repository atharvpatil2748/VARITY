"""Chunker drafts and central materialization (contract 05, owner Piyush).

``GeneralChunker.chunk(parsed, version_id)`` emits ordered ``ChunkDraft``
JSON instances (dicts) with contiguous valid block spans. Chunkers never
assign IDs: the central materializer (``CentralMaterializer``) assigns the
``Locator``, ``ordinal``, ``chunk_id`` and ``schema_version`` using the
injected canonical ID maker (``verity.ids`` from Atharv's PR-A1) and attaches
the explicit ``requirement_id`` on requirement chunks from
``source_id + local_id`` (``verity.ids.make_requirement_id``).

Guarantees:

* Drafts cite only a contiguous valid block span; chunks never span pages
  and never cross structural headings (one requirement/entity section, or
  one heading path for general content).
* Requirement chunks contain the requirement title, normative text,
  constraints and edge cases (contract 04). Acceptance criteria and API
  definitions get their own chunks. ``# References`` and general document
  content become ``general_chunk``; code files become ``code_chunk``.
* ``CHUNKING_ERROR`` for invalid spans or empty output when parsed text
  exists.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Mapping
from uuid import UUID

from ._compat import VerityError

CHUNKER_VERSION = "1.0"

#: Internal target: general chunks stay under this many characters while
#: remaining inside one heading path and one page (contract 05 leaves the
#: token-size heuristic internal).
MAX_CHUNK_CHARS = 2000


def _chunking_error(message: str, details: Mapping[str, Any] | None = None) -> VerityError:
    return VerityError("CHUNKING_ERROR", message, dict(details or {}))


class GeneralChunker:
    """Contract-16 ``Chunker``: parsed document -> ordered chunk drafts.

    ``requirement_ids`` optionally maps ``local_id`` to its ``req_`` hash so
    requirement drafts can carry ``requirement_id`` before the central
    materializer runs (it is always attached there as well, from the
    explicit ``source_id + local_id`` pair).
    """

    def __init__(self, requirement_ids: Mapping[str, str] | None = None) -> None:
        self._requirement_ids = dict(requirement_ids or {})

    def chunk(self, parsed: Mapping[str, Any], version_id: UUID) -> tuple[dict, ...]:
        blocks = list(parsed.get("blocks", []))
        if not blocks:
            return ()
        drafts: list[tuple[int, dict]] = []
        covered: set[int] = set()
        if parsed.get("kind") == "spec":
            for record, kind in self._spec_spans(parsed):
                span_start, span_end = record["block_start"], record["block_end"]
                self._validate_span(blocks, span_start, span_end)
                requirement_id = None
                if kind == "requirement":
                    requirement_id = self._requirement_ids.get(record["local_id"])
                draft = {
                    "kind": kind,
                    "text": self._spec_chunk_text(kind, record),
                    "block_start": span_start,
                    "block_end": span_end,
                    "start_offset": None,
                    "end_offset": None,
                    "requirement_id": requirement_id,
                }
                drafts.append((span_start, draft))
                covered.update(range(span_start, span_end + 1))

        code_only = all(b.get("block_type") == "code" for b in blocks) and not drafts
        general_kind = "code_chunk" if code_only else "general_chunk"
        index = 0
        while index < len(blocks):
            if index in covered:
                index += 1
                continue
            groups = self._take_groups(blocks, covered, index)
            for start, end in groups:
                drafts.append((start, self._make_draft(blocks, start, end, general_kind)))
            index = groups[-1][1] + 1

        drafts.sort(key=lambda item: item[0])
        result = tuple(draft for _, draft in drafts)
        if blocks and not result:
            raise _chunking_error(
                "chunker produced no chunks for nonempty parsed document"
            )
        return result

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _spec_spans(parsed: Mapping[str, Any]):
        for record in parsed.get("spec_requirements", []):
            yield record, "requirement"
        for record in parsed.get("spec_entities", []):
            yield record, record["kind"]  # api_definition | acceptance_criterion

    @staticmethod
    def _spec_chunk_text(kind: str, record: Mapping[str, Any]) -> str:
        if kind == "requirement":
            parts = [record["title"], record["text"]]
            if record.get("constraints"):
                parts.append("Constraints:")
                parts.extend(f"- {item}" for item in record["constraints"])
            if record.get("edge_cases"):
                parts.append("Edge cases:")
                parts.extend(f"- {item}" for item in record["edge_cases"])
            return "\n".join(parts)
        return f"{record['title']}\n{record['text']}"

    @staticmethod
    def _validate_span(blocks: list[dict], start: int, end: int) -> None:
        if start < 0 or end < start or end >= len(blocks):
            raise _chunking_error(
                "chunk block span is invalid",
                {"block_start": start, "block_end": end},
            )
        pages = {block.get("page") for block in blocks[start:end + 1]}
        if len(pages) > 1:
            raise _chunking_error("chunk span crosses pages", {"block_start": start})

    def _take_groups(self, blocks: list[dict], covered: set[int],
                     start: int) -> list[tuple[int, int]]:
        """Split the run from ``start`` into chunks of one page+heading path."""
        page = blocks[start].get("page")
        path = list(blocks[start].get("heading_path", []))
        groups: list[tuple[int, int]] = []
        run_start = start
        size = 0
        index = start
        while index < len(blocks) and index not in covered:
            block = blocks[index]
            same = (block.get("page") == page
                    and list(block.get("heading_path", [])) == path)
            if not same:
                break
            text_len = len(block.get("text", ""))
            if size + text_len > MAX_CHUNK_CHARS and index > run_start:
                groups.append((run_start, index - 1))
                run_start = index
                size = 0
            size += text_len
            index += 1
        groups.append((run_start, index - 1))
        return groups

    @staticmethod
    def _make_draft(blocks: list[dict], start: int, end: int, kind: str) -> dict:
        text = "\n".join(blocks[i]["text"] for i in range(start, end + 1))
        return {
            "kind": kind,
            "text": text,
            "block_start": start,
            "block_end": end,
            "start_offset": None,
            "end_offset": None,
            "requirement_id": None,
        }


class CentralMaterializer:
    """Converts drafts to canonical ``Chunk``/``Requirement``/``SpecEntity``.

    The injected ``id_maker`` supplies the canonical ID functions from
    ``verity.ids`` (contract 16, Atharv's PR-A1): ``make_block_id``,
    ``make_chunk_id``, ``make_requirement_id``, ``make_evidence_id``. This
    class is the single place where IDs are assigned (contract 05); parsers
    and chunkers never assign IDs.

    Output records are canonical JSON instances (dicts) of the contract
    03/21 models: ``blocks`` carry their ``block_id``; ``chunks``,
    ``requirements`` and ``spec_entities`` match ``$defs/Chunk``,
    ``$defs/Requirement`` and ``$defs/SpecEntity``.
    """

    def __init__(self, id_maker: Any) -> None:
        self._ids = id_maker

    def materialize(
        self,
        parsed: Mapping[str, Any],
        drafts: tuple[Mapping[str, Any], ...],
        source_id: UUID | str,
        document_id: UUID | str,
        version_id: UUID | str,
        source_path: str,
    ) -> dict[str, list]:
        blocks = list(parsed.get("blocks", []))
        req_by_span, ent_by_span = self._index_spec_records(parsed)
        req_id_by_local: dict[str, str] = {}
        for record in parsed.get("spec_requirements", []):
            req_id_by_local[record["local_id"]] = self._ids.make_requirement_id(
                source_id, record["local_id"]
            )

        block_rows = [
            dict(block, block_id=self._ids.make_block_id(version_id, block["ordinal"], block["text"]))
            for block in blocks
        ]

        chunk_rows: list[dict] = []
        chunks_by_span: dict[tuple[int, int], dict] = {}
        for ordinal, draft in enumerate(drafts):
            span = (draft["block_start"], draft["block_end"])
            locator = self._locator(blocks, span, source_id, document_id,
                                    version_id, source_path)
            requirement_id = draft.get("requirement_id")
            if requirement_id is None and span in req_by_span:
                requirement_id = req_id_by_local[req_by_span[span]["local_id"]]
            chunk_id = self._ids.make_chunk_id(version_id, self._as_draft(draft))
            row = {
                "schema_version": "1.0.0",
                "chunk_id": chunk_id,
                "kind": draft["kind"],
                "text": draft["text"],
                "locator": locator,
                "block_start": draft["block_start"],
                "block_end": draft["block_end"],
                "ordinal": ordinal,
                "requirement_id": requirement_id,
            }
            chunk_rows.append(row)
            chunks_by_span[span] = row

        requirement_rows = self._requirements(
            parsed, chunks_by_span, req_id_by_local, source_id, document_id,
            version_id, source_path,
        )
        entity_rows = self._entities(
            parsed, chunks_by_span, req_id_by_local, source_id, document_id,
            version_id, source_path,
        )
        return {
            "blocks": block_rows,
            "chunks": chunk_rows,
            "requirements": requirement_rows,
            "spec_entities": entity_rows,
        }

    # -- helpers ----------------------------------------------------------
    @staticmethod
    def _as_draft(draft: Mapping[str, Any]) -> Any:
        """Attribute-access view of a draft dict for ``verity.ids.make_chunk_id``."""
        return SimpleNamespace(
            kind=draft["kind"],
            text=draft["text"],
            block_start=draft["block_start"],
            block_end=draft["block_end"],
            start_offset=draft["start_offset"],
            end_offset=draft["end_offset"],
            requirement_id=draft.get("requirement_id"),
        )

    @staticmethod
    def _index_spec_records(parsed: Mapping[str, Any]):
        req_by_span: dict[tuple[int, int], dict] = {}
        for record in parsed.get("spec_requirements", []):
            req_by_span[(record["block_start"], record["block_end"])] = record
        ent_by_span: dict[tuple[int, int], dict] = {}
        for record in parsed.get("spec_entities", []):
            ent_by_span[(record["block_start"], record["block_end"])] = record
        return req_by_span, ent_by_span

    @staticmethod
    def _locator(blocks: list[dict], span: tuple[int, int], source_id: Any,
                 document_id: Any, version_id: Any, source_path: str) -> dict:
        start, end = span
        span_blocks = blocks[start:end + 1]
        pages = {block.get("page") for block in span_blocks}
        if len(pages) > 1:
            raise _chunking_error("locator span crosses pages", {"block_start": start})
        lines = [b["start_line"] for b in span_blocks if b.get("start_line") is not None]
        ends = [b["end_line"] for b in span_blocks if b.get("end_line") is not None]
        return {
            "source_id": str(source_id),
            "document_id": str(document_id),
            "version_id": str(version_id),
            "source_path": source_path,
            "page": pages.pop() if len(pages) == 1 else None,
            "heading_path": list(span_blocks[0].get("heading_path", [])),
            "start_line": min(lines) if lines else None,
            "end_line": max(ends) if ends else None,
            "start_offset": None,
            "end_offset": None,
        }

    @staticmethod
    def _normative_end(blocks: list[dict], record: Mapping[str, Any]) -> int:
        """Last block of the requirement's normative text (heading-level path)."""
        first = blocks[record["block_start"]]
        path = list(first.get("heading_path", []))
        end = record["block_start"]
        for index in range(record["block_start"], record["block_end"] + 1):
            if list(blocks[index].get("heading_path", [])) == path:
                end = index
        return end

    def _requirements(self, parsed, chunks_by_span, req_id_by_local,
                      source_id, document_id, version_id, source_path) -> list[dict]:
        blocks = list(parsed.get("blocks", []))
        entities = {
            record["local_id"]: record for record in parsed.get("spec_entities", [])
        }
        rows: list[dict] = []
        for record in parsed.get("spec_requirements", []):
            local_id = record["local_id"]
            span = (record["block_start"], record["block_end"])
            chunk = chunks_by_span.get(span)
            if chunk is None:
                raise _chunking_error(
                    "requirement has no chunk for its block span",
                    {"local_id": local_id},
                )
            norm_end = self._normative_end(blocks, record)
            locator = self._locator(blocks, (record["block_start"], norm_end),
                                   source_id, document_id, version_id, source_path)
            criteria = []
            for ac_id in record.get("acceptance_local_ids", []):
                ac = entities.get(ac_id)
                if ac is None:
                    raise VerityError(
                        "SPEC_VALIDATION_ERROR",
                        f"acceptance criterion {ac_id} is not defined",
                        {"local_id": ac_id},
                    )
                criteria.append({
                    "local_id": ac["local_id"],
                    "title": ac["title"],
                    "text": ac["text"],
                    "locator": self._locator(
                        blocks, (ac["block_start"], ac["block_end"]),
                        source_id, document_id, version_id, source_path),
                })
            rows.append({
                "schema_version": "1.0.0",
                "requirement_id": req_id_by_local[local_id],
                "local_id": local_id,
                "source_id": str(source_id),
                "document_id": str(document_id),
                "version_id": str(version_id),
                "title": record["title"],
                "text": record["text"],
                "constraints": list(record.get("constraints", [])),
                "edge_cases": list(record.get("edge_cases", [])),
                "acceptance_criteria": criteria,
                "api_refs": list(record.get("api_refs", [])),
                "reference_ids": list(record.get("reference_ids", [])),
                "chunk_id": chunk["chunk_id"],
                "evidence_id": self._ids.make_evidence_id(version_id, chunk["chunk_id"]),
                "locator": locator,
            })
        return rows

    def _entities(self, parsed, chunks_by_span, req_id_by_local,
                  source_id, document_id, version_id, source_path) -> list[dict]:
        blocks = list(parsed.get("blocks", []))
        rows: list[dict] = []
        for record in parsed.get("spec_entities", []):
            span = (record["block_start"], record["block_end"])
            chunk = chunks_by_span.get(span)
            if chunk is None:
                raise _chunking_error(
                    "spec entity has no chunk for its block span",
                    {"local_id": record["local_id"]},
                )
            for ref in record.get("reference_ids", []):
                if ref not in req_id_by_local:
                    raise VerityError(
                        "SPEC_VALIDATION_ERROR",
                        f"reference to unknown requirement {ref}",
                        {"local_id": ref},
                    )
            rows.append({
                "schema_version": "1.0.0",
                "kind": record["kind"],
                "local_id": record["local_id"],
                "title": record["title"],
                "text": record["text"],
                "reference_ids": list(record.get("reference_ids", [])),
                "chunk_id": chunk["chunk_id"],
                "evidence_id": self._ids.make_evidence_id(version_id, chunk["chunk_id"]),
                "locator": self._locator(blocks, span, source_id, document_id,
                                         version_id, source_path),
            })
        return rows