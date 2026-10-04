"""Strict VERITY spec schema v1 validator and requirement parser.

Contract: Docs/contracts/04_VERITY_SPEC_SCHEMA.md. Owner Piyush.

Accepts UTF-8 Markdown with YAML front matter and mandatory headings only.
Rejects duplicate IDs, dangling references, empty normative text and
malformed metadata with line-numbered ``SPEC_VALIDATION_ERROR``; it never
invents requirement IDs.
"""

from __future__ import annotations

from typing import Any

from ..errors import VerityError
from ..models import SpecEntityDraft

#: Mandatory front-matter keys (contract 04).
REQUIRED_METADATA_KEYS = ("verity_spec", "project", "title", "version", "source_id")

#: Allowed top-level sections.
ALLOWED_SECTIONS = ("Requirements", "API definitions", "Acceptance criteria", "References")

#: Allowed requirement children headings.
ALLOWED_CHILDREN = ("Constraints", "Edge cases", "References")


def validate_spec_document(text: str) -> list[SpecEntityDraft]:
    """Parse and validate a v1 spec; return entity drafts or raise ``VerityError``.

    Skeleton for Phase 11 hour 1-2: implement front-matter parsing, ID
    validation (``^(REQ|API|AC)-[0-9]{3,}$``), reference resolution and
    block-span extraction per contract 04.
    """
    raise VerityError(
        "SPEC_VALIDATION_ERROR",
        "spec parser not yet implemented (scheduled Phase 11, contract 04)",
    )