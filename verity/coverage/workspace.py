"""Workspace snapshot values and scanner protocol (contract 16).

``WorkspaceSnapshot = {workspace_id, root, revision, files}`` and
``WorkspaceFile = {relative_path, content_sha256, size}`` are internal
values produced by ``WorkspaceScanner`` (contract 16); the root is never
serialized publicly.

D2 (open): contract 12 restricts file reads to the scanner, but the
frozen snapshot carries no file text. Until contract 16 is amended,
``CodeEvidenceRetriever`` implementations work from fake snapshots in
tests and from metadata-only evidence in production.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..errors import VerityError
from ..ids import canonical_digest

#: Contract 12 safety caps (real walker arrives in N2).
MAX_FILE_BYTES = 1024 * 1024
MAX_FILES = 5000


@dataclass(frozen=True)
class WorkspaceFile:
    """One safe snapshot entry: path, content hash and size only."""

    relative_path: str
    content_sha256: str
    size: int

    def __post_init__(self) -> None:
        if not self.relative_path or "\\" in self.relative_path or \
                self.relative_path.startswith("/") or ".." in self.relative_path.split("/"):
            raise VerityError(
                "INVALID_REQUEST",
                "relative_path must be a safe POSIX-relative path",
                {"relative_path": self.relative_path},
            )
        if len(self.content_sha256) != 64 or \
                any(c not in "0123456789abcdef" for c in self.content_sha256):
            raise VerityError(
                "INVALID_REQUEST",
                "content_sha256 must be 64 lowercase hex",
                {"content_sha256": self.content_sha256},
            )
        if self.size < 0 or self.size > MAX_FILE_BYTES:
            raise VerityError(
                "INVALID_REQUEST",
                f"size must be 0..{MAX_FILE_BYTES}",
                {"size": self.size},
            )


@dataclass(frozen=True)
class WorkspaceSnapshot:
    """Scanner output: identity, resolved root, manifest hash and files."""

    workspace_id: str
    root: Path
    revision: str
    files: tuple[WorkspaceFile, ...]

    def __post_init__(self) -> None:
        if not self.workspace_id:
            raise VerityError("INVALID_REQUEST", "workspace_id must be nonempty")
        if len(self.revision) != 64:
            raise VerityError("INVALID_REQUEST", "revision must be 64 hex chars")
        if len(self.files) > MAX_FILES:
            raise VerityError(
                "LIMIT_EXCEEDED",
                f"snapshot exceeds {MAX_FILES} files (contract 12)",
            )


def manifest_revision(files: tuple[WorkspaceFile, ...]) -> str:
    """Deterministic workspace revision: hash of the sorted file manifest.

    Contract 12: hash of the sorted relative-path/content-hash manifest,
    computed before and after evaluation to detect mid-scan changes.
    """
    payload = [
        {"path": f.relative_path, "sha256": f.content_sha256, "size": f.size}
        for f in sorted(files, key=lambda f: f.relative_path)
    ]
    return canonical_digest({"files": payload})


class WorkspaceScanner:
    """Contract 16 protocol. The real safe walker is N2."""

    async def snapshot(self, workspace_id: str) -> WorkspaceSnapshot:
        raise NotImplementedError


class FakeSnapshotScanner(WorkspaceScanner):
    """N1 fake: snapshots an explicit manifest, no filesystem walking.

    ``snapshots`` maps workspace_id -> file tuple; when ``mutate_after``
    is set, the *next* snapshot for that workspace returns the mutated
    manifest so tests can exercise the contract-12 workspace-changed rule.
    """

    def __init__(
        self,
        snapshots: dict[str, tuple[WorkspaceFile, ...]],
        roots: dict[str, Path] | None = None,
        mutate_after: dict[str, tuple[WorkspaceFile, ...]] | None = None,
    ) -> None:
        self._snapshots = dict(snapshots)
        self._roots = dict(roots or {})
        self._mutate_after = dict(mutate_after or {})
        self._pending: dict[str, tuple[WorkspaceFile, ...]] = {}

    async def snapshot(self, workspace_id: str) -> WorkspaceSnapshot:
        try:
            files = self._snapshots[workspace_id]
        except KeyError:
            raise VerityError(
                "WORKSPACE_NOT_FOUND",
                f"workspace {workspace_id!r} is not configured",
                {"workspace_id": workspace_id},
            ) from None
        root = self._roots.get(workspace_id, Path("."))
        revision = manifest_revision(files)
        if workspace_id in self._mutate_after:
            # Return current revision, but stage the changed manifest for
            # the next call so the coverage service detects the drift.
            if workspace_id in self._pending:
                self._snapshots[workspace_id] = self._pending.pop(workspace_id)
                files = self._snapshots[workspace_id]
                revision = manifest_revision(files)
            else:
                self._pending[workspace_id] = self._mutate_after[workspace_id]
        return WorkspaceSnapshot(
            workspace_id=workspace_id, root=root, revision=revision, files=files
        )