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

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from ..config import VerityConfig, WorkspaceConfig
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

    async def read_lines(
        self,
        snapshot: WorkspaceSnapshot,
        relative_path: str,
        start_line: int,
        end_line: int,
    ) -> str:
        """Scanner-owned bounded text read (D2, contract 16 change log 1.0.4).

        Frozen rules: only this method and ``snapshot`` perform workspace
        I/O; ``relative_path`` must be an exact ``snapshot.files`` member;
        ``1 <= start_line <= end_line``; each call is capped at 200 lines
        and 8,000 characters (``LIMIT_EXCEEDED`` beyond); the file's
        ``content_sha256`` is verified against the manifest first and a
        mismatch raises ``COVERAGE_UNAVAILABLE`` (treated as
        ``workspace_changed`` -> ``UNCERTAIN`` by the coverage service).
        """
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


#: Contract-12 read caps frozen by the D2 amendment (contract 16, 1.0.4).
MAX_READ_LINES = 200
MAX_READ_CHARS = 8000

#: Extensions never indexed as text (contract 12: ignore binaries).
_BINARY_EXTENSIONS = frozenset({
    ".bin", ".exe", ".dll", ".so", ".dylib", ".png", ".jpg", ".jpeg",
    ".gif", ".pdf", ".zip", ".gz", ".tar", ".7z", ".pyc", ".class",
    ".woff", ".woff2", ".ico", ".mp3", ".mp4",
})


class RealWorkspaceScanner(WorkspaceScanner):
    """N2: the real safe scanner (contract 12).

    Only this class opens workspace files. It resolves the configured
    root for ``workspace_id`` from ``VerityConfig``, rejects missing
    roots and symlink escapes, ignores configured excludes (``.git``,
    virtual environments, dependencies, dists), skips binaries and
    oversized files, caps the scan at 5,000 files and hashes the sorted
    manifest as the deterministic ``workspace_revision``.
    """

    def __init__(
        self,
        config: VerityConfig,
        *,
        max_files: int = MAX_FILES,
        max_file_bytes: int = MAX_FILE_BYTES,
    ) -> None:
        self._config = config
        self._max_files = max_files
        self._max_file_bytes = max_file_bytes

    async def snapshot(self, workspace_id: str) -> WorkspaceSnapshot:
        workspace = self._config.workspace(workspace_id)
        excludes = set(workspace.exclude) | {".git", ".venv"}
        root = self._safe_root(workspace)
        files: list[WorkspaceFile] = []
        for current, dirnames, filenames in os.walk(root):
            current_path = Path(current)
            # Prune excluded/symlinked directories in place.
            kept: list[str] = []
            for name in list(dirnames):
                child = current_path / name
                if name in excludes or child.is_symlink():
                    if child.is_symlink() and not self._inside(root, child):
                        raise VerityError(
                            "WORKSPACE_DENIED",
                            "workspace directory escapes the root via symlink",
                            {"relative_path": self._relative(root, child)},
                        )
                    continue
                kept.append(name)
            dirnames[:] = sorted(kept)
            for name in sorted(filenames):
                path = current_path / name
                if path.is_symlink():
                    if not self._inside(root, path):
                        raise VerityError(
                            "WORKSPACE_DENIED",
                            "workspace file escapes the root via symlink",
                            {"relative_path": self._relative(root, path)},
                        )
                    continue  # in-root symlinks are skipped, never followed
                try:
                    size = path.stat().st_size
                except OSError as exc:
                    raise VerityError(
                        "COVERAGE_UNAVAILABLE",
                        "workspace file became unreadable during scan",
                        {"relative_path": self._relative(root, path)},
                    ) from exc
                if size > self._max_file_bytes:
                    continue
                if path.suffix.lower() in _BINARY_EXTENSIONS:
                    continue
                data = path.read_bytes()
                if b"\x00" in data[:1024]:
                    continue  # binary sniff: no OCR, no claims
                files.append(
                    WorkspaceFile(
                        relative_path=self._relative(root, path),
                        content_sha256=hashlib.sha256(data).hexdigest(),
                        size=len(data),
                    )
                )
                if len(files) > self._max_files:
                    raise VerityError(
                        "LIMIT_EXCEEDED",
                        f"workspace exceeds {self._max_files} files (contract 12)",
                        {"workspace_id": workspace_id},
                    )
        manifest = tuple(sorted(files, key=lambda f: f.relative_path))
        return WorkspaceSnapshot(
            workspace_id=workspace_id,
            root=root,
            revision=manifest_revision(manifest),
            files=manifest,
        )

    async def read_lines(
        self,
        snapshot: WorkspaceSnapshot,
        relative_path: str,
        start_line: int,
        end_line: int,
    ) -> str:
        """Contract-16 D2 (1.0.4) bounded scanner-owned read; see protocol."""
        members = {f.relative_path: f for f in snapshot.files}
        entry = members.get(relative_path)
        if entry is None:
            raise VerityError(
                "INVALID_REQUEST",
                "relative_path is not a member of the snapshot manifest",
                {"relative_path": relative_path},
            )
        if start_line < 1 or end_line < 1 or start_line > end_line:
            raise VerityError(
                "INVALID_REQUEST",
                "require 1 <= start_line <= end_line",
                {"start_line": start_line, "end_line": end_line},
            )
        if end_line - start_line + 1 > MAX_READ_LINES:
            raise VerityError(
                "LIMIT_EXCEEDED",
                f"read exceeds {MAX_READ_LINES} lines (contract 16, 1.0.4)",
                {"start_line": start_line, "end_line": end_line},
            )
        path = snapshot.root / relative_path
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest != entry.content_sha256:
            # File changed since the snapshot was taken: never return
            # stale text as if it matched the manifest (D2 rule 4).
            raise VerityError(
                "COVERAGE_UNAVAILABLE",
                "workspace file changed since the snapshot was taken",
                {"relative_path": relative_path},
            )
        lines = data.decode("utf-8", errors="replace").splitlines(keepends=True)
        text = "".join(lines[start_line - 1:end_line])
        if len(text) > MAX_READ_CHARS:
            raise VerityError(
                "LIMIT_EXCEEDED",
                f"read exceeds {MAX_READ_CHARS} characters (contract 16, 1.0.4)",
                {"start_line": start_line, "end_line": end_line},
            )
        return text

    def _safe_root(self, workspace: WorkspaceConfig) -> Path:
        configured = workspace.root
        if configured.is_symlink():
            raise VerityError(
                "WORKSPACE_DENIED",
                "workspace root must not be a symlink",
                {"workspace_id": workspace.workspace_id},
            )
        root = configured.resolve()
        if not root.is_dir():
            raise VerityError(
                "WORKSPACE_NOT_FOUND",
                "workspace root is missing or not a directory",
                {"workspace_id": workspace.workspace_id},
            )
        return root

    @staticmethod
    def _inside(root: Path, candidate: Path) -> bool:
        try:
            candidate.resolve().relative_to(root)
            return True
        except ValueError:
            return False

    @staticmethod
    def _relative(root: Path, path: Path) -> str:
        return path.relative_to(root).as_posix()