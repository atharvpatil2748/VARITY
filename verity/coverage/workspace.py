"""Workspace root safety and snapshot.

Contract: Docs/contracts/12_VERITY_COVERAGE_CONTRACT.md. Owner Vanashree.

Resolve every candidate path inside the configured workspace root and
reject traversal, symlink escapes, excluded/vendor directories, generated
binaries and oversized files. ``workspace_id`` maps only through the
configured allowlist; arbitrary caller paths are forbidden.
"""

from __future__ import annotations

from pathlib import Path

from ..config import WorkspaceConfig


def resolve_workspace_root(workspace: WorkspaceConfig) -> Path:
    """Return the validated canonical workspace root.

    Raises ``WORKSPACE_DENIED`` when the root is missing, escapes itself
    via symlink, or is not a directory.
    """
    from ..errors import VerityError

    root = workspace.root.resolve()
    if not root.is_dir():
        raise VerityError(
            "WORKSPACE_DENIED",
            f"workspace root {workspace.workspace_id!r} is not a directory",
            {"workspace_id": workspace.workspace_id},
        )
    if root != workspace.root or root.is_symlink():
        raise VerityError(
            "WORKSPACE_DENIED",
            "workspace root must not be a symlink escape",
            {"workspace_id": workspace.workspace_id},
        )
    return root