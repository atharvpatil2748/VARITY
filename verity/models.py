"""VERITY canonical data models (contract 03, machine schemas contract 21).

Single model authority: JSON property names are snake_case, UTC times are
RFC 3339 with ``Z``, strings are UTF-8, ``null`` is explicit, omitted
required properties are invalid. Arrays default to ``[]`` where stated.
Unknown enum values fail v1 parsing. Objects do not allow unspecified
fields on the v1 wire.
"""

from __future__ import annotations

import json
import os
import re
import types
from dataclasses import MISSING, dataclass, field, fields, is_dataclass
from enum import Enum
from typing import Any, Mapping, Union, get_args, get_origin, get_type_hints

from .errors import VerityError

SCHEMA_VERSION = "1.0.0"

UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
LOCAL_ID_RE = re.compile(r"^REQ-[0-9]{3,}$")
ACCEPTANCE_CRITERION_RE = re.compile(r"^AC-[0-9]{3,}$")
API_LOCAL_ID_RE = re.compile(r"^API-[0-9]{3,}$")
DATETIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
SOURCE_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class DocumentKind(str, Enum):
    SPEC = "spec"
    GENERAL = "general"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    READY = "ready"
    PARTIAL = "partial"
    FAILED = "failed"


class ChunkKind(str, Enum):
    REQUIREMENT = "requirement"
    ACCEPTANCE_CRITERION = "acceptance_criterion"
    API_DEFINITION = "api_definition"
    GENERAL_CHUNK = "general_chunk"
    CODE_CHUNK = "code_chunk"


class CoverageStatus(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    UNCERTAIN = "UNCERTAIN"


class RetrievalMode(str, Enum):
    HYBRID = "hybrid"
    LEXICAL_ONLY = "lexical_only"
    SEMANTIC_ONLY = "semantic_only"


class Completeness(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    EMPTY = "empty"


class EvidenceBasis(str, Enum):
    TEXT_MATCH = "text_match"
    SYMBOL_MATCH = "symbol_match"
    STATIC_CHECK = "static_check"
    TEST_EXECUTION = "test_execution"


class TestOutcome(str, Enum):
    NOT_RUN = "not_run"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class IngestMode(str, Enum):
    AUTO = "auto"
    SPEC = "spec"
    GENERAL = "general"


def _check(condition: bool, message: str, field_name: str) -> None:
    if not condition:
        raise VerityError("INVALID_REQUEST", message, {"field": field_name})


def _validate(annotation: Any, value: Any, path: str) -> Any:
    if annotation is Any:
        return value
    origin = get_origin(annotation)
    if annotation is Union or origin is types.UnionType:
        all_args = get_args(annotation)
        args = [a for a in all_args if a is not type(None)]
        if value is None:
            if type(None) in all_args:
                return None
            raise VerityError(
                "INVALID_REQUEST", f"{path} must not be null", details={"field": path}
            )
        if len(args) == 1:
            return _validate(args[0], value, path)
        for option in args:
            try:
                return _validate(option, value, path)
            except VerityError:
                continue
        raise VerityError(
            "INVALID_REQUEST", f"{path} has wrong type", details={"field": path}
        )
    if origin in (list, tuple):
        _check(isinstance(value, (list, tuple)), f"{path} must be an array", path)
        (item_type,) = get_args(annotation)
        return [
            _validate(item_type, item, f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(annotation, type):
        if issubclass(annotation, VerityModel):
            return annotation.from_dict(value)
        if issubclass(annotation, Enum):
            _check(isinstance(value, str), f"{path} must be a string", path)
            try:
                return annotation(value)
            except ValueError:
                raise VerityError(
                    "INVALID_REQUEST",
                    f"{path} has unknown enum value",
                    {"field": path, "value": value},
                ) from None
        if annotation is str:
            _check(isinstance(value, str), f"{path} must be a string", path)
            return value
        if annotation is bool:
            _check(isinstance(value, bool), f"{path} must be a boolean", path)
            return value
        if annotation in (int, float):
            _check(
                isinstance(value, annotation) and not isinstance(value, bool),
                f"{path} has wrong type",
                path,
            )
            return value
    raise VerityError(
        "INVALID_REQUEST",
        f"{path} has unsupported annotation {annotation!r}",
        details={"field": path},
    )


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: _jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    """Canonical JSON text: sorted keys, no ASCII escaping, compact separators."""
    return json.dumps(
        _jsonable(value), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


class VerityModel:
    """Base for canonical models: strict from_dict and canonical to_dict.

    Every declared dataclass field must be present in the wire dict unless it
    has a Python default (contract defaults such as ``[]`` are encoded as
    dataclass defaults). Unknown keys are rejected. Nullable fields are
    required but may be ``None``. Validation failures raise
    ``VerityError("INVALID_REQUEST", ...)``.
    """

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(self)  # type: ignore[return-value]

    @classmethod
    def from_dict(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise VerityError(
                "INVALID_REQUEST",
                f"{cls.__name__} requires a JSON object",
                details={"expected": cls.__name__},
            )
        hints = get_type_hints(cls)
        known = {f.name for f in fields(cls)}  # type: ignore[arg-type]
        unknown = set(data) - known
        if unknown:
            raise VerityError(
                "INVALID_REQUEST",
                f"{cls.__name__} has unknown fields",
                details={"unknown_fields": sorted(unknown)},
            )
        kwargs: dict[str, Any] = {}
        for f in fields(cls):  # type: ignore[arg-type]
            if f.name not in data:
                if f.default is not MISSING or f.default_factory is not MISSING:
                    continue
                raise VerityError(
                    "INVALID_REQUEST",
                    f"{cls.__name__}.{f.name} is required",
                    details={"field": f.name},
                )
            kwargs[f.name] = _validate(hints[f.name], data[f.name], f.name)
        model = cls(**kwargs)  # type: ignore[call-arg]
        model.validate()  # type: ignore[attr-defined]
        return model

    def validate(self) -> None:
        """Hook for cross-field invariants; default does nothing."""


def _uuid_str(value: str, path: str) -> str:
    _check(bool(UUID4_RE.fullmatch(value)), f"{path} must be a UUIDv4 string", path)
    return value


def _hex_str(value: str, path: str) -> str:
    _check(bool(SHA256_RE.fullmatch(value)), f"{path} must be 64 lowercase hex", path)
    return value


def _nonempty(value: str, path: str) -> str:
    _check(isinstance(value, str) and value != "", f"{path} must be nonempty", path)
    return value


def _datetime_str(value: str, path: str) -> str:
    _check(
        isinstance(value, str) and bool(DATETIME_RE.fullmatch(value)),
        f"{path} must be RFC 3339 UTC with Z",
        path,
    )
    return value


def _is_abs_path(path: str) -> bool:
    return os.path.isabs(path) or ":" in path.split("/", 1)[0] or path.startswith("\\")


# ---------------------------------------------------------------------------
# Canonical models (contract 03)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Source(VerityModel):
    schema_version: str
    source_id: str
    source_key: str | None
    source_path: str
    registered_at: str

    def validate(self) -> None:
        _check(self.schema_version == SCHEMA_VERSION,
               "schema_version must be 1.0.0", "schema_version")
        _uuid_str(self.source_id, "source_id")
        _check(
            self.source_key is None or bool(SOURCE_KEY_RE.fullmatch(self.source_key)),
            "source_key must match the human slug pattern",
            "source_key",
        )
        _check(self.source_path != "" and not _is_abs_path(self.source_path),
               "source_path must be relative to the configured root", "source_path")
        _datetime_str(self.registered_at, "registered_at")


@dataclass(frozen=True)
class DocumentMetadata(VerityModel):
    metadata_version: str
    title: str | None
    source_key: str | None
    project: str | None
    spec_version: str | None
    language: str | None
    page_count: int | None
    parser_name: str
    parser_version: str
    warnings: list[str] = field(default_factory=list)

    def validate(self) -> None:
        _check(self.metadata_version == SCHEMA_VERSION,
               "metadata_version must be 1.0.0", "metadata_version")
        _check(
            self.page_count is None or self.page_count >= 1,
            "page_count must be integer >=1 or null",
            "page_count",
        )
        _nonempty(self.parser_name, "parser_name")
        _nonempty(self.parser_version, "parser_version")


@dataclass(frozen=True)
class Document(VerityModel):
    schema_version: str
    document_id: str
    source_id: str
    version_id: str
    name: str
    media_type: str
    kind: DocumentKind
    status: DocumentStatus
    content_sha256: str
    metadata: DocumentMetadata
    indexed_at: str | None

    def validate(self) -> None:
        _check(self.schema_version == SCHEMA_VERSION,
               "schema_version must be 1.0.0", "schema_version")
        _uuid_str(self.document_id, "document_id")
        _uuid_str(self.source_id, "source_id")
        _uuid_str(self.version_id, "version_id")
        _nonempty(self.name, "name")
        _nonempty(self.media_type, "media_type")
        _hex_str(self.content_sha256, "content_sha256")
        _check(
            self.indexed_at is None or bool(DATETIME_RE.fullmatch(self.indexed_at)),
            "indexed_at must be RFC 3339 UTC with Z or null",
            "indexed_at",
        )


@dataclass(frozen=True)
class Locator(VerityModel):
    source_id: str
    document_id: str
    version_id: str
    source_path: str
    page: int | None
    start_line: int | None
    end_line: int | None
    start_offset: int | None
    end_offset: int | None
    heading_path: list[str] = field(default_factory=list)

    def validate(self) -> None:
        _uuid_str(self.source_id, "source_id")
        _uuid_str(self.document_id, "document_id")
        _uuid_str(self.version_id, "version_id")
        _check(not _is_abs_path(self.source_path) and self.source_path != "",
               "source_path must be relative", "source_path")
        _check(self.page is None or self.page >= 1, "page must be >=1 or null", "page")
        _check(self.start_line is None or self.start_line >= 1,
               "start_line must be >=1 or null", "start_line")
        _check(self.end_line is None or self.end_line >= 1,
               "end_line must be >=1 or null", "end_line")
        _check(self.start_offset is None or self.start_offset >= 0,
               "start_offset must be >=0 or null", "start_offset")
        _check(self.end_offset is None or self.end_offset >= 0,
               "end_offset must be >=0 or null", "end_offset")
        # start/end pairs are jointly present or null and ordered (contract 03).
        _check(
            (self.start_line is None) == (self.end_line is None),
            "start_line/end_line must be jointly present or null",
            "start_line",
        )
        _check(
            (self.start_offset is None) == (self.end_offset is None),
            "start_offset/end_offset must be jointly present or null",
            "start_offset",
        )
        _check(
            self.start_line is None or self.end_line is None
            or self.start_line <= self.end_line,
            "start_line must be <= end_line",
            "start_line",
        )
        _check(
            self.start_offset is None or self.end_offset is None
            or self.start_offset <= self.end_offset,
            "start_offset must be <= end_offset",
            "start_offset",
        )


@dataclass(frozen=True)
class Requirement(VerityModel):
    schema_version: str
    requirement_id: str
    local_id: str
    source_id: str
    document_id: str
    version_id: str
    title: str
    text: str
    chunk_id: str
    evidence_id: str
    locator: Locator
    constraints: list[str] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)
    api_refs: list[str] = field(default_factory=list)
    reference_ids: list[str] = field(default_factory=list)

    def validate(self) -> None:
        _check(self.schema_version == SCHEMA_VERSION,
               "schema_version must be 1.0.0", "schema_version")
        _check(self.requirement_id.startswith("req_"),
               "requirement_id must be req_ hash", "requirement_id")
        _check(bool(LOCAL_ID_RE.fullmatch(self.local_id)),
               "local_id must match REQ-[0-9]{3,}", "local_id")
        _uuid_str(self.source_id, "source_id")
        _uuid_str(self.document_id, "document_id")
        _uuid_str(self.version_id, "version_id")
        _nonempty(self.title, "title")
        _nonempty(self.text, "text")
        _check(self.chunk_id.startswith("chk_"),
               "chunk_id must be chk_ hash", "chunk_id")
        _check(self.evidence_id.startswith("ev_"),
               "evidence_id must be ev_ hash", "evidence_id")


@dataclass(frozen=True)
class AcceptanceCriterion(VerityModel):
    local_id: str
    title: str
    text: str
    locator: Locator

    def validate(self) -> None:
        _check(bool(ACCEPTANCE_CRITERION_RE.fullmatch(self.local_id)),
               "local_id must match AC-[0-9]{3,}", "local_id")
        _nonempty(self.title, "title")
        _nonempty(self.text, "text")


@dataclass(frozen=True)
class SpecEntity(VerityModel):
    schema_version: str
    kind: ChunkKind
    local_id: str
    title: str
    text: str
    chunk_id: str
    evidence_id: str
    locator: Locator
    reference_ids: list[str] = field(default_factory=list)

    def validate(self) -> None:
        _check(self.schema_version == SCHEMA_VERSION,
               "schema_version must be 1.0.0", "schema_version")
        _check(
            self.kind in (ChunkKind.API_DEFINITION, ChunkKind.ACCEPTANCE_CRITERION),
            "SpecEntity.kind must be api_definition or acceptance_criterion",
            "kind",
        )
        if self.kind == ChunkKind.API_DEFINITION:
            _check(bool(API_LOCAL_ID_RE.fullmatch(self.local_id)),
                   "API entity local_id must match API-[0-9]{3,}", "local_id")
        else:
            _check(bool(ACCEPTANCE_CRITERION_RE.fullmatch(self.local_id)),
                   "AC entity local_id must match AC-[0-9]{3,}", "local_id")
        _nonempty(self.title, "title")
        _nonempty(self.text, "text")
        _check(self.chunk_id.startswith("chk_"), "chunk_id must be chk_ hash",
               "chunk_id")
        _check(self.evidence_id.startswith("ev_"), "evidence_id must be ev_ hash",
               "evidence_id")


# ---------------------------------------------------------------------------
# Ingestion drafts (contract 05; internal cross-module data contracts)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SpecRequirementDraft(VerityModel):
    local_id: str
    title: str
    text: str
    block_start: int
    block_end: int
    constraints: list[str] = field(default_factory=list)
    edge_cases: list[str] = field(default_factory=list)
    api_refs: list[str] = field(default_factory=list)
    reference_ids: list[str] = field(default_factory=list)
    acceptance_local_ids: list[str] = field(default_factory=list)

    def validate(self) -> None:
        _check(bool(LOCAL_ID_RE.fullmatch(self.local_id)),
               "local_id must match REQ-[0-9]{3,}", "local_id")
        _nonempty(self.title, "title")
        _nonempty(self.text, "text")
        _check(self.block_start >= 0, "block_start must be >=0", "block_start")
        _check(self.block_end >= 0, "block_end must be >=0", "block_end")
        _check(self.block_start <= self.block_end,
               "block_start must be <= block_end", "block_start")


@dataclass(frozen=True)
class SpecEntityDraft(VerityModel):
    kind: ChunkKind
    local_id: str
    title: str
    text: str
    block_start: int
    block_end: int
    reference_ids: list[str] = field(default_factory=list)

    def validate(self) -> None:
        _check(
            self.kind in (ChunkKind.API_DEFINITION, ChunkKind.ACCEPTANCE_CRITERION),
            "SpecEntityDraft.kind must be api_definition or acceptance_criterion",
            "kind",
        )
        _nonempty(self.local_id, "local_id")
        _nonempty(self.title, "title")
        _nonempty(self.text, "text")
        _check(self.block_start >= 0, "block_start must be >=0", "block_start")
        _check(self.block_end >= 0, "block_end must be >=0", "block_end")
        _check(self.block_start <= self.block_end,
               "block_start must be <= block_end", "block_start")


@dataclass(frozen=True)
class ParsedBlock(VerityModel):
    ordinal: int
    text: str
    block_type: str
    page: int | None
    start_line: int | None
    end_line: int | None
    start_offset: int | None
    end_offset: int | None
    heading_path: list[str] = field(default_factory=list)

    def validate(self) -> None:
        _check(self.ordinal >= 0, "ordinal must be >=0", "ordinal")
        _nonempty(self.text, "text")
        _check(self.block_type in ("paragraph", "heading", "code"),
               "block_type must be paragraph|heading|code", "block_type")
        _check(self.page is None or self.page >= 1, "page must be >=1 or null", "page")
        _check(self.start_line is None or self.start_line >= 1,
               "start_line must be >=1 or null", "start_line")
        _check(self.end_line is None or self.end_line >= 1,
               "end_line must be >=1 or null", "end_line")
        _check(
            (self.start_line is None) == (self.end_line is None),
            "start_line/end_line must be jointly present or null",
            "start_line",
        )


@dataclass(frozen=True)
class ParsedDocument(VerityModel):
    metadata: DocumentMetadata
    blocks: list[ParsedBlock]
    media_type: str
    kind: DocumentKind
    spec_requirements: list[SpecRequirementDraft] = field(default_factory=list)
    spec_entities: list[SpecEntityDraft] = field(default_factory=list)

    def validate(self) -> None:
        _nonempty(self.media_type, "media_type")
        for index, block in enumerate(self.blocks):
            _check(block.ordinal == index,
                   "block ordinals must be contiguous from zero",
                   f"blocks[{index}].ordinal")


@dataclass(frozen=True)
class ChunkDraft(VerityModel):
    kind: ChunkKind
    text: str
    block_start: int
    block_end: int
    start_offset: int | None
    end_offset: int | None
    requirement_id: str | None

    def validate(self) -> None:
        _nonempty(self.text, "text")
        _check(self.block_start >= 0, "block_start must be >=0", "block_start")
        _check(self.block_end >= 0, "block_end must be >=0", "block_end")
        _check(self.block_start <= self.block_end,
               "block_start must be <= block_end", "block_start")
        _check(
            self.start_offset is None or self.start_offset >= 0,
            "start_offset must be >=0 or null",
            "start_offset",
        )
        _check(
            self.end_offset is None or self.end_offset >= 0,
            "end_offset must be >=0 or null",
            "end_offset",
        )
        _check(
            (self.start_offset is None) == (self.end_offset is None),
            "start_offset/end_offset must be jointly present or null",
            "start_offset",
        )
        _check(
            self.requirement_id is None or self.requirement_id.startswith("req_"),
            "requirement_id must be req_ hash or null",
            "requirement_id",
        )


# ---------------------------------------------------------------------------
# Chunks, evidence and retrieval results (contracts 03, 06, 07)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Chunk(VerityModel):
    schema_version: str
    chunk_id: str
    kind: ChunkKind
    text: str
    locator: Locator
    block_start: int
    block_end: int
    ordinal: int
    requirement_id: str | None

    def validate(self) -> None:
        _check(self.schema_version == SCHEMA_VERSION,
               "schema_version must be 1.0.0", "schema_version")
        _check(self.chunk_id.startswith("chk_"), "chunk_id must be chk_ hash",
               "chunk_id")
        _nonempty(self.text, "text")
        _check(self.block_start >= 0, "block_start must be >=0", "block_start")
        _check(self.block_end >= 0, "block_end must be >=0", "block_end")
        _check(self.block_start <= self.block_end,
               "block_start must be <= block_end", "block_start")
        _check(self.ordinal >= 0, "ordinal must be >=0", "ordinal")
        _check(
            self.requirement_id is None or self.requirement_id.startswith("req_"),
            "requirement_id must be req_ hash or null",
            "requirement_id",
        )


@dataclass(frozen=True)
class Provenance(VerityModel):
    schema_version: str
    content_sha256: str
    parser_name: str
    parser_version: str
    chunker_version: str
    embedding_model: str | None
    indexed_at: str

    def validate(self) -> None:
        _check(self.schema_version == SCHEMA_VERSION,
               "schema_version must be 1.0.0", "schema_version")
        _hex_str(self.content_sha256, "content_sha256")
        _nonempty(self.parser_name, "parser_name")
        _nonempty(self.parser_version, "parser_version")
        _nonempty(self.chunker_version, "chunker_version")
        _datetime_str(self.indexed_at, "indexed_at")


@dataclass(frozen=True)
class Citation(VerityModel):
    evidence_id: str
    label: str
    locator: Locator

    def validate(self) -> None:
        _check(self.evidence_id.startswith("ev_"),
               "evidence_id must be ev_ hash", "evidence_id")
        _nonempty(self.label, "label")


@dataclass(frozen=True)
class Ranking(VerityModel):
    dense_rank: int | None
    lexical_rank: int | None
    rrf_score: float | None
    rerank_score: float | None

    def validate(self) -> None:
        _check(self.dense_rank is None or self.dense_rank >= 1,
               "dense_rank must be >=1 or null", "dense_rank")
        _check(self.lexical_rank is None or self.lexical_rank >= 1,
               "lexical_rank must be >=1 or null", "lexical_rank")


@dataclass(frozen=True)
class Evidence(VerityModel):
    schema_version: str
    evidence_id: str
    chunk_id: str
    kind: ChunkKind
    quote: str
    requirement_id: str | None
    citation: Citation
    provenance: Provenance
    score: float | None
    ranking: Ranking

    def validate(self) -> None:
        _check(self.schema_version == SCHEMA_VERSION,
               "schema_version must be 1.0.0", "schema_version")
        _check(self.evidence_id.startswith("ev_"),
               "evidence_id must be ev_ hash", "evidence_id")
        _check(self.chunk_id.startswith("chk_"), "chunk_id must be chk_ hash",
               "chunk_id")
        _nonempty(self.quote, "quote")
        _check(
            self.requirement_id is None or self.requirement_id.startswith("req_"),
            "requirement_id must be req_ hash or null",
            "requirement_id",
        )


@dataclass(frozen=True)
class EvidenceLookup(VerityModel):
    schema_version: str
    evidence: Evidence
    context_before: str
    context_after: str

    def validate(self) -> None:
        _check(self.schema_version == SCHEMA_VERSION,
               "schema_version must be 1.0.0", "schema_version")


@dataclass(frozen=True)
class SearchRequest(VerityModel):
    query: str
    document_ids: list[str] | None
    document_kinds: list[DocumentKind] | None
    chunk_kinds: list[ChunkKind] | None
    limit: int = 8
    per_document_limit: int | None = None

    def validate(self) -> None:
        _check(2 <= len(self.query) <= 2000,
               "query length must be 2-2000", "query")
        _check(
            self.document_ids is None or (len(self.document_ids) > 0),
            "document_ids null means all; an empty array is invalid",
            "document_ids",
        )
        if self.document_ids is not None:
            for index, identifier in enumerate(self.document_ids):
                _uuid_str(identifier, f"document_ids[{index}]")
        _check(1 <= self.limit <= 20, "limit must be 1-20", "limit")
        _check(
            self.per_document_limit is None or 1 <= self.per_document_limit <= 20,
            "per_document_limit must be 1-20 or null",
            "per_document_limit",
        )


# ---------------------------------------------------------------------------
# Retrieval, ingestion, coverage and error results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetrievalResult(VerityModel):
    chunk: Chunk
    score: float
    dense_rank: int | None
    lexical_rank: int | None
    rrf_score: float | None
    rerank_score: float | None

    def validate(self) -> None:
        _check(self.dense_rank is None or self.dense_rank >= 1,
               "dense_rank must be >=1 or null", "dense_rank")
        _check(self.lexical_rank is None or self.lexical_rank >= 1,
               "lexical_rank must be >=1 or null", "lexical_rank")
        # All four ranking fields are required on the wire (contract 21);
        # rrf_score is required and non-null (contract 03).
        _check(self.rrf_score is not None, "rrf_score must not be null",
               "rrf_score")


@dataclass(frozen=True)
class RetrievalRun(VerityModel):
    items: list[RetrievalResult]
    retrieval_mode: RetrievalMode
    reranker_used: bool
    completeness: Completeness
    omissions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SearchResult(VerityModel):
    schema_version: str
    query: str
    retrieval_mode: RetrievalMode
    completeness: Completeness
    total_returned: int
    items: list[Evidence] = field(default_factory=list)
    reranker_used: bool = False
    omissions: list[str] = field(default_factory=list)

    def validate(self) -> None:
        _check(self.schema_version == SCHEMA_VERSION,
               "schema_version must be 1.0.0", "schema_version")
        _check(self.total_returned == len(self.items),
               "total_returned must equal items.length", "total_returned")


@dataclass(frozen=True)
class IngestRequest(VerityModel):
    source_path: str
    mode: IngestMode = IngestMode.AUTO
    source_id: str | None = None

    def validate(self) -> None:
        _check(self.source_path != "" and not _is_abs_path(self.source_path),
               "source_path must be relative to the configured root", "source_path")
        _check(
            self.source_id is None or bool(UUID4_RE.fullmatch(self.source_id)),
            "source_id must be UUIDv4 or null",
            "source_id",
        )


@dataclass(frozen=True)
class IngestResult(VerityModel):
    document: Document
    created_new_version: bool


@dataclass(frozen=True)
class ListPage(VerityModel):
    """Generic list page: ``{items, total, limit, offset}`` (contract 11)."""

    items: list
    total: int
    limit: int
    offset: int = 0

    def validate(self) -> None:
        _check(self.total >= 0, "total must be >=0", "total")
        _check(self.limit >= 1, "limit must be >=1", "limit")
        _check(self.offset >= 0, "offset must be >=0", "offset")


@dataclass(frozen=True)
class CodeEvidence(VerityModel):
    path: str
    start_line: int
    end_line: int
    excerpt: str
    basis: EvidenceBasis

    def validate(self) -> None:
        _check(self.path != "" and not _is_abs_path(self.path),
               "path must be relative", "path")
        _check(self.start_line >= 1, "start_line must be >=1", "start_line")
        _check(self.end_line >= 1, "end_line must be >=1", "end_line")
        _check(self.start_line <= self.end_line,
               "start_line must be <= end_line", "start_line")
        _nonempty(self.excerpt, "excerpt")


@dataclass(frozen=True)
class TestEvidence(VerityModel):
    path: str
    start_line: int
    end_line: int
    excerpt: str
    basis: EvidenceBasis
    outcome: TestOutcome = TestOutcome.NOT_RUN

    def validate(self) -> None:
        _check(self.path != "" and not _is_abs_path(self.path),
               "path must be relative", "path")
        _check(self.start_line >= 1, "start_line must be >=1", "start_line")
        _check(self.end_line >= 1, "end_line must be >=1", "end_line")
        _check(self.start_line <= self.end_line,
               "start_line must be <= end_line", "start_line")
        _nonempty(self.excerpt, "excerpt")


@dataclass(frozen=True)
class RequirementCoverage(VerityModel):
    requirement_id: str
    status: CoverageStatus
    reason: str
    implementation: list[CodeEvidence] = field(default_factory=list)
    tests: list[TestEvidence] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def validate(self) -> None:
        _check(self.requirement_id.startswith("req_"),
               "requirement_id must be req_ hash", "requirement_id")
        _nonempty(self.reason, "reason")


@dataclass(frozen=True)
class CoverageRequest(VerityModel):
    requirement_ids: list[str] | None
    workspace_id: str
    run_tests: bool = False

    def validate(self) -> None:
        _check(
            self.requirement_ids is None or len(self.requirement_ids) > 0,
            "requirement_ids null means all; an empty array is invalid",
            "requirement_ids",
        )
        if self.requirement_ids is not None:
            for index, identifier in enumerate(self.requirement_ids):
                _check(identifier.startswith("req_"),
                       f"requirement_ids[{index}] must be req_ hash",
                       f"requirement_ids[{index}]")
        _nonempty(self.workspace_id, "workspace_id")


@dataclass(frozen=True)
class CoverageResult(VerityModel):
    schema_version: str
    coverage_id: str
    workspace_id: str
    workspace_revision: str
    inspected_at: str
    results: list[RequirementCoverage] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def validate(self) -> None:
        _check(self.schema_version == SCHEMA_VERSION,
               "schema_version must be 1.0.0", "schema_version")
        _uuid_str(self.coverage_id, "coverage_id")
        _nonempty(self.workspace_id, "workspace_id")
        _hex_str(self.workspace_revision, "workspace_revision")
        _datetime_str(self.inspected_at, "inspected_at")


@dataclass(frozen=True)
class Error(VerityModel):
    schema_version: str
    code: str
    message: str
    request_id: str
    details: dict[str, Any] | None = None
    retryable: bool = False

    def validate(self) -> None:
        from .errors import ERROR_CODES

        _check(self.schema_version == SCHEMA_VERSION,
               "schema_version must be 1.0.0", "schema_version")
        _check(self.code in ERROR_CODES, "code must be a v1 error code", "code")
        _nonempty(self.message, "message")
        _uuid_str(self.request_id, "request_id")