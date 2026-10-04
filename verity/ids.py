"""Canonical deterministic ID functions.

Contract: Docs/contracts/03_VERITY_DATA_SCHEMAS.md (identifier registry).

All SHA-256 inputs use UTF-8 canonical JSON with sorted keys,
``ensure_ascii=false``, separators ``,`` and ``:``, and NFC-normalized
string values. Exact payloads:

* block      ``{"version_id":uuid,"ordinal":n,"text":text}``
* chunk      ``{"version_id":uuid,"block_start":n,"block_end":n,"start_offset":n|null,"end_offset":n|null,"kind":kind,"text":text}``
* requirement ``{"source_id":uuid,"local_id":local_id}``
* evidence   ``{"version_id":uuid,"chunk_id":chunk_id}``

Hash the encoded JSON bytes, then prepend ``blk_``, ``chk_``, ``req_`` or
``ev_``. No module independently invents ID hashing.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any, Mapping
from uuid import UUID, uuid4

from .models import ChunkDraft

_HEX64 = "0123456789abcdef"


def _nfc(value: Any) -> Any:
    """Recursively NFC-normalize all string values in a JSON payload."""
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, dict):
        return {key: _nfc(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_nfc(item) for item in value]
    return value


def canonical_digest(payload: Mapping[str, Any]) -> str:
    """Return the 64 lowercase hex SHA-256 of the canonical JSON payload."""
    text = json.dumps(
        _nfc(payload), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def new_uuid4() -> UUID:
    """Create a new UUIDv4 for source/document/version/session/request IDs."""
    return uuid4()


def make_block_id(version_id: UUID, ordinal: int, text: str) -> str:
    """Deterministic version-specific block ID: ``blk_`` + 64 lowercase hex."""
    payload = {"version_id": str(version_id), "ordinal": ordinal, "text": text}
    return "blk_" + canonical_digest(payload)


def make_chunk_id(version_id: UUID, draft: ChunkDraft) -> str:
    """Deterministic version-specific chunk ID from a materializable draft."""
    payload = {
        "version_id": str(version_id),
        "block_start": draft.block_start,
        "block_end": draft.block_end,
        "start_offset": draft.start_offset,
        "end_offset": draft.end_offset,
        "kind": draft.kind.value if hasattr(draft.kind, "value") else draft.kind,
        "text": draft.text,
    }
    return "chk_" + canonical_digest(payload)


def make_requirement_id(source_id: UUID, local_id: str) -> str:
    """Stable requirement ID: SHA-256 of source ID and authored ``local_id``."""
    payload = {"source_id": str(source_id), "local_id": local_id}
    return "req_" + canonical_digest(payload)


def make_evidence_id(version_id: UUID, chunk_id: str) -> str:
    """Stable evidence ID for one immutable ``(version_id, chunk_id)`` pair."""
    payload = {"version_id": str(version_id), "chunk_id": chunk_id}
    return "ev_" + canonical_digest(payload)