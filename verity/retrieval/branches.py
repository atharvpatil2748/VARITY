"""Internal candidate-branch records (contract 06; P6, owner Piyush).

Not wire types and not part of the frozen public surface: retrieval internals
are explicitly free (contract 01 change boundary). ``BranchResult`` carries
one branch's ranked candidate stream plus truthful omission labels — a failed
branch degrades with an omission and never fabricates results (contract 06:
"a failed branch may degrade ... with an omission").

Omission labels are internal capability names (contract 03: ``omissions`` is
"missing capability names"); P7 fusion concatenates them for the final run.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models import SearchRequest
from ..storage.base import RankedChunk

#: Lexical branch could not produce candidates (store/index failure).
LEXICAL_UNAVAILABLE = "lexical_unavailable"
#: No embedding model is provisioned (offline, never downloaded at serving).
SEMANTIC_MODEL_UNAVAILABLE = "semantic_model_unavailable"
#: Model ran but the vector candidate path failed.
SEMANTIC_UNAVAILABLE = "semantic_unavailable"

#: Contract 06: up to 50 lexical and 50 semantic candidates after filters.
BRANCH_CANDIDATE_BUDGET = 50


@dataclass(frozen=True)
class BranchResult:
    """One branch's output: ranked candidates (ranks normalized 1..n) + omissions."""

    items: tuple[RankedChunk, ...] = ()
    omissions: tuple[str, ...] = ()


def normalize(stream: tuple[RankedChunk, ...], budget: int) -> tuple[RankedChunk, ...]:
    """Cap the stream at ``budget`` and re-number branch ranks from 1 (contract 06)."""
    capped = stream[:budget]
    return tuple(
        RankedChunk(chunk=ranked.chunk, rank=index, raw_score=ranked.raw_score)
        for index, ranked in enumerate(capped, start=1)
    )


def filters_of(request: SearchRequest) -> dict:
    """Snapshot of the request's filter fields (test/debug aid)."""
    return {
        "document_ids": request.document_ids,
        "document_kinds": request.document_kinds,
        "chunk_kinds": request.chunk_kinds,
        "limit": request.limit,
        "per_document_limit": request.per_document_limit,
    }