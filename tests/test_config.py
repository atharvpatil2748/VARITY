"""Config contract tests: defaults, unknown keys, env overrides, workspaces."""

from __future__ import annotations

from pathlib import Path

import pytest

from verity.config import VerityConfig, load_config
from verity.errors import VerityError


def test_missing_config_uses_defaults(tmp_path: Path) -> None:
    config = load_config(path=tmp_path / "absent.toml", environ={})
    assert isinstance(config, VerityConfig)
    assert config.search_limit_default == 8
    assert config.search_limit_max == 20
    assert config.api_host == "127.0.0.1"
    assert config.mcp_transport == "stdio"
    assert config.embedding_required is False
    assert config.workspaces == {}


def test_valid_config_file(tmp_path: Path) -> None:
    workspace = tmp_path / "demo-workspace"
    workspace.mkdir()
    config_file = tmp_path / "verity.toml"
    config_file.write_text(
        'config_version = "1.0.0"\n'
        'data_dir = "./data"\n'
        "search_limit_default = 5\n"
        "search_limit_max = 10\n"
        "\n[workspaces.demo]\n"
        'root = "./demo-workspace"\n'
        'test_command = ["python", "-m", "pytest", "-q"]\n',
        encoding="utf-8",
    )
    config = load_config(path=config_file, environ={})
    assert config.search_limit_default == 5
    assert config.search_limit_max == 10
    assert config.workspaces["demo"].root == workspace.resolve()
    assert config.workspaces["demo"].test_command == ("python", "-m", "pytest", "-q")


def test_unknown_top_level_key_rejected(tmp_path: Path) -> None:
    config_file = tmp_path / "verity.toml"
    config_file.write_text('bogus_key = true\n', encoding="utf-8")
    with pytest.raises(VerityError) as exc:
        load_config(path=config_file, environ={})
    assert exc.value.code == "CONFIG_INVALID"


def test_non_loopback_host_rejected(tmp_path: Path) -> None:
    config_file = tmp_path / "verity.toml"
    config_file.write_text('api_host = "0.0.0.0"\n', encoding="utf-8")
    with pytest.raises(VerityError) as exc:
        load_config(path=config_file, environ={})
    assert exc.value.code == "CONFIG_INVALID"


def test_mcp_transport_must_be_stdio(tmp_path: Path) -> None:
    config_file = tmp_path / "verity.toml"
    config_file.write_text('mcp_transport = "http"\n', encoding="utf-8")
    with pytest.raises(VerityError):
        load_config(path=config_file, environ={})


def test_rerank_candidates_bound(tmp_path: Path) -> None:
    config_file = tmp_path / "verity.toml"
    config_file.write_text(
        "lexical_candidates = 5\nsemantic_candidates = 5\nrerank_candidates = 30\n",
        encoding="utf-8",
    )
    with pytest.raises(VerityError):
        load_config(path=config_file, environ={})


def test_workspace_root_must_exist(tmp_path: Path) -> None:
    config_file = tmp_path / "verity.toml"
    config_file.write_text(
        '[workspaces.demo]\nroot = "./missing"\n', encoding="utf-8"
    )
    with pytest.raises(VerityError):
        load_config(path=config_file, environ={})


def test_env_overrides(tmp_path: Path) -> None:
    config = load_config(
        path=tmp_path / "absent.toml",
        environ={
            "VERITY_LOG_LEVEL": "DEBUG",
            "VERITY_API_PORT": "9000",
            "VERITY_RERANKER_ENABLED": "false",
        },
    )
    assert config.log_level == "DEBUG"
    assert config.api_port == 9000
    assert config.reranker_enabled is False


def test_invalid_env_rejected(tmp_path: Path) -> None:
    with pytest.raises(VerityError):
        load_config(
            path=tmp_path / "absent.toml",
            environ={"VERITY_API_PORT": "99999"},
        )
    with pytest.raises(VerityError):
        load_config(
            path=tmp_path / "absent.toml",
            environ={"VERITY_API_HOST": "0.0.0.0"},
        )


def test_workspace_lookup_raises_typed_error(tmp_path: Path) -> None:
    config = load_config(path=tmp_path / "absent.toml", environ={})
    with pytest.raises(VerityError) as exc:
        config.workspace("demo")
    assert exc.value.code == "WORKSPACE_NOT_FOUND"