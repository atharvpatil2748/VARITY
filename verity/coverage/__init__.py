"""VERITY coverage subpackage (owner Vanashree).

Contract 12 (coverage) and contract 16 (public interfaces), Phase 9
structure. N1 scope: frozen protocol shapes, contract-12 status rules and
fixture-driven fakes. The real directory-walking scanner is N2; real
candidate excerpts are N3 (blocked by D2); real store persistence is N6.
"""

from .workspace import (
    WorkspaceFile,
    WorkspaceScanner,
    WorkspaceSnapshot,
    FakeSnapshotScanner,
    RealWorkspaceScanner,
    manifest_revision,
)
from .candidates import CodeEvidenceRetriever, FakeCodeEvidenceRetriever
from .evaluator import DefaultRequirementEvaluator, RequirementEvaluator
from .service import CoverageService, FakeCoverageService

__all__ = [
    "WorkspaceFile",
    "WorkspaceScanner",
    "WorkspaceSnapshot",
    "FakeSnapshotScanner",
    "RealWorkspaceScanner",
    "manifest_revision",
    "CodeEvidenceRetriever",
    "FakeCodeEvidenceRetriever",
    "RequirementEvaluator",
    "DefaultRequirementEvaluator",
    "CoverageService",
    "FakeCoverageService",
]