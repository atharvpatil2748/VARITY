"""N2 scanner tests: real safe walker over contract-12 rules."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from verity.config import VerityConfig, WorkspaceConfig
from verity.coverage import RealWorkspaceScanner, manifest_revision
from verity.errors import VerityError

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "coverage_workspace"


def config_with(root: Path, **overrides) -> VerityConfig:
    workspace = WorkspaceConfig(
        workspace_id="demo",
        root=root,
        test_command=(),
        exclude=tuple(overrides.pop("exclude", (".git", ".venv", "node_modules", "dist"))),
    )
    values = {
        "config_dir": Path("."),
        "workspaces": {"demo": workspace},
    }
    values.update(overrides)
    return VerityConfig(**values)


def run(coro):
    return asyncio.run(coro)


def test_real_scanner_snapshots_fixture_workspace(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    (root / "src").mkdir(parents=True)
    (root / "src" / "app.py").write_text("def app():\n    return 1\n", encoding="utf-8")
    scanner = RealWorkspaceScanner(config_with(root))
    snapshot = run(scanner.snapshot("demo"))
    assert [f.relative_path for f in snapshot.files] == ["src/app.py"]
    assert snapshot.revision == manifest_revision(snapshot.files)
    assert snapshot.revision != "0" * 64


def test_real_scanner_ignores_excludes_binaries_and_oversized(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    for name in (".git", "node_modules", "src", "assets"):
        (root / name).mkdir(parents=True)
    (root / ".git" / "config.py").write_text("x = 1\n", encoding="utf-8")
    (root / "node_modules" / "dep.py").write_text("x = 2\n", encoding="utf-8")
    (root / "src" / "app.py").write_text("x = 3\n", encoding="utf-8")
    (root / "assets" / "logo.png").write_bytes(b"\x89PNG fake")
    (root / "big.txt").write_bytes(b"a" * (1024 * 1024 + 1))
    scanner = RealWorkspaceScanner(config_with(root))
    snapshot = run(scanner.snapshot("demo"))
    assert [f.relative_path for f in snapshot.files] == ["src/app.py"]


def test_real_scanner_binary_sniff_skips_nul_files(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "plain.dat").write_bytes(b"\x00\x01binary")
    (root / "text.dat").write_text("plain text", encoding="utf-8")
    scanner = RealWorkspaceScanner(config_with(root))
    snapshot = run(scanner.snapshot("demo"))
    assert [f.relative_path for f in snapshot.files] == ["text.dat"]


def test_real_scanner_rejects_missing_root(tmp_path: Path) -> None:
    scanner = RealWorkspaceScanner(config_with(tmp_path / "nope"))
    with pytest.raises(VerityError) as exc_info:
        run(scanner.snapshot("demo"))
    assert exc_info.value.code == "WORKSPACE_NOT_FOUND"


def test_real_scanner_rejects_unknown_workspace(tmp_path: Path) -> None:
    scanner = RealWorkspaceScanner(config_with(tmp_path))
    with pytest.raises(VerityError) as exc_info:
        run(scanner.snapshot("other"))
    assert exc_info.value.code == "WORKSPACE_NOT_FOUND"


def test_real_scanner_enforces_file_cap(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    for index in range(4):
        (root / f"f{index}.py").write_text(f"x = {index}\n", encoding="utf-8")
    scanner = RealWorkspaceScanner(config_with(root), max_files=3)
    with pytest.raises(VerityError) as exc_info:
        run(scanner.snapshot("demo"))
    assert exc_info.value.code == "LIMIT_EXCEEDED"


def test_real_scanner_revision_changes_with_content(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    scanner = RealWorkspaceScanner(config_with(root))
    first = run(scanner.snapshot("demo"))
    (root / "a.py").write_text("x = 2\n", encoding="utf-8")
    second = run(scanner.snapshot("demo"))
    assert first.revision != second.revision


def test_real_scanner_skips_in_root_symlink(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    (root / "src").mkdir(parents=True)
    (root / "src" / "real.py").write_text("x = 1\n", encoding="utf-8")
    try:
        (root / "src" / "link.py").symlink_to(root / "src" / "real.py")
    except OSError:
        pytest.skip("symlinks unavailable on this platform/privilege")
    scanner = RealWorkspaceScanner(config_with(root))
    snapshot = run(scanner.snapshot("demo"))
    assert [f.relative_path for f in snapshot.files] == ["src/real.py"]