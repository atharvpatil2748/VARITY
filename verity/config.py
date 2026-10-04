"""VERITY configuration parsing (contract 14, v1.0.0, owner Atharv).

One ``verity.toml`` is authoritative; environment variables override named
scalar fields only. Missing config uses contract defaults. Secrets are
env-only. The parser rejects unknown keys and invalid values with
``CONFIG_INVALID``. Modules receive a frozen ``VerityConfig`` object and
never read ``os.environ`` independently.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from .errors import VerityError

CONFIG_VERSION = "1.0.0"
WORKSPACE_ID_RE = r"^[a-z][a-z0-9_-]{0,31}$"

import re as _re

_ALLOWED_KEYS = frozenset({
    "config_version", "data_dir", "source_root", "database_path",
    "embedding_model", "reranker_model", "embedding_required",
    "reranker_enabled", "search_limit_default", "search_limit_max",
    "lexical_candidates", "semantic_candidates", "rerank_candidates",
    "api_host", "api_port", "mcp_transport", "log_level",
})
_BOOL_FIELDS = frozenset({"embedding_required", "reranker_enabled"})
_INT_FIELDS = frozenset({
    "search_limit_default", "search_limit_max", "lexical_candidates",
    "semantic_candidates", "rerank_candidates", "api_port",
})
_STR_FIELDS = frozenset({
    "config_version", "data_dir", "source_root", "database_path",
    "embedding_model", "reranker_model", "api_host", "mcp_transport",
    "log_level",
})


@dataclass(frozen=True)
class WorkspaceConfig:
    """One configured workspace root: ``root``, optional ``test_command``, ``exclude``."""

    workspace_id: str
    root: Path
    test_command: tuple[str, ...] = ()
    exclude: tuple[str, ...] = (".git", ".venv", "node_modules", "dist")


def _invalid(message: str, details: Mapping[str, Any] | None = None) -> VerityError:
    return VerityError("CONFIG_INVALID", message, details)


@dataclass(frozen=True)
class VerityConfig:
    """Frozen configuration object passed to modules (never re-parsed)."""

    config_version: str = CONFIG_VERSION
    data_dir: Path = Path("./data")
    source_root: Path = Path("./documents")
    database_path: Path = Path("./data/verity.sqlite3")
    embedding_model: str = "BAAI/bge-m3@pinned-local-revision"
    reranker_model: str = "BAAI/bge-reranker-v2-m3@pinned-local-revision"
    embedding_required: bool = False
    reranker_enabled: bool = True
    search_limit_default: int = 8
    search_limit_max: int = 20
    lexical_candidates: int = 50
    semantic_candidates: int = 50
    rerank_candidates: int = 30
    api_host: str = "127.0.0.1"
    api_port: int = 8765
    mcp_transport: str = "stdio"
    log_level: str = "INFO"
    config_dir: Path = Path(".")
    workspaces: dict[str, WorkspaceConfig] = field(default_factory=dict)
    cline_provider_id: str | None = None
    cline_model_id: str | None = None

    def workspace(self, workspace_id: str) -> WorkspaceConfig:
        try:
            return self.workspaces[workspace_id]
        except KeyError:
            raise VerityError(
                "WORKSPACE_NOT_FOUND",
                f"workspace {workspace_id!r} is not configured",
                {"workspace_id": workspace_id},
            ) from None


def _resolve(config_dir: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = config_dir / path
    return path.resolve()


def _invalid(message: str, details: Mapping[str, Any] | None = None) -> VerityError:
    return VerityError("CONFIG_INVALID", message, details)


def _parse_scalars(raw: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for key in _STR_FIELDS:
        if key in raw and not isinstance(raw[key], str):
            raise _invalid(f"{key} must be a string", {"field": key})
        elif key in raw:
            values[key] = raw[key]
    for key in _BOOL_FIELDS:
        if key in raw and not isinstance(raw[key], bool):
            raise _invalid(f"{key} must be a boolean", {"field": key})
        elif key in raw:
            values[key] = raw[key]
    for key in _INT_FIELDS:
        if key in raw:
            if not isinstance(raw[key], int) or isinstance(raw[key], bool):
                raise _invalid(f"{key} must be an integer", {"field": key})
            values[key] = raw[key]

    if "config_version" in values and values["config_version"] != CONFIG_VERSION:
        raise _invalid("config_version must be 1.0.0", {"field": "config_version"})
    for key in ("search_limit_default", "search_limit_max", "lexical_candidates",
                "semantic_candidates", "rerank_candidates"):
        if key in values and values[key] < 1:
            raise _invalid(f"{key} must be positive", {"field": key})
    if "search_limit_max" in values and values["search_limit_max"] > 20:
        raise _invalid("search_limit_max is capped at 20",
                       {"field": "search_limit_max"})
    if "search_limit_default" in values and "search_limit_max" in values:
        if values["search_limit_default"] > values["search_limit_max"]:
            raise _invalid("search_limit_default must be <= search_limit_max",
                          {"field": "search_limit_default"})
    lexical = values.get("lexical_candidates", 50)
    semantic = values.get("semantic_candidates", 50)
    if "rerank_candidates" in values and values["rerank_candidates"] > lexical + semantic:
        raise _invalid(
            "rerank_candidates must be <= lexical_candidates+semantic_candidates",
            {"field": "rerank_candidates"},
        )
    if "api_port" in values and not 1 <= values["api_port"] <= 65535:
        raise _invalid("api_port must be 1-65535", {"field": "api_port"})
    if "mcp_transport" in values and values["mcp_transport"] != "stdio":
        raise _invalid("mcp_transport accepts only stdio in v1",
                       {"field": "mcp_transport"})
    if "log_level" in values and values["log_level"] not in ("DEBUG", "INFO",
                                                             "WARNING", "ERROR"):
        raise _invalid("log_level must be DEBUG|INFO|WARNING|ERROR",
                       {"field": "log_level"})
    if "api_host" in values and values["api_host"] != "127.0.0.1":
        raise _invalid("non-loopback api_host is invalid in v1",
                       {"field": "api_host"})
    return values


def _parse_workspaces(raw: Any, config_dir: Path) -> dict[str, WorkspaceConfig]:
    workspaces: dict[str, WorkspaceConfig] = {}
    ws_raw = raw.get("workspaces", {})
    if not isinstance(ws_raw, dict):
        raise _invalid("workspaces must be a table", {"field": "workspaces"})
    for workspace_id, entry in ws_raw.items():
        if not _re.fullmatch(WORKSPACE_ID_RE, workspace_id):
            raise _invalid(
                "workspace IDs must match ^[a-z][a-z0-9_-]{0,31}$",
                {"workspace_id": workspace_id},
            )
        if not isinstance(entry, dict):
            raise _invalid("workspace entry must be a table",
                          {"workspace_id": workspace_id})
        unknown = set(entry) - {"root", "test_command", "exclude"}
        if unknown:
            raise _invalid("workspace entry has unknown keys",
                           {"workspace_id": workspace_id,
                            "unknown_keys": sorted(unknown)})
        if "root" not in entry:
            raise _invalid("workspace entry requires root",
                          {"workspace_id": workspace_id})
        root = _resolve(config_dir, entry["root"])
        if not root.is_dir():
            raise _invalid("workspace root must resolve to an existing directory",
                           {"workspace_id": workspace_id})
        test_command = entry.get("test_command", [])
        if not isinstance(test_command, list) or not all(
            isinstance(item, str) for item in test_command
        ):
            raise _invalid("test_command must be an argument array",
                           {"workspace_id": workspace_id})
        exclude = entry.get("exclude", [".git", ".venv", "node_modules", "dist"])
        if not isinstance(exclude, list) or not all(
            isinstance(item, str) for item in exclude
        ):
            raise _invalid("exclude must be a string array",
                           {"workspace_id": workspace_id})
        workspaces[workspace_id] = WorkspaceConfig(
            workspace_id=workspace_id,
            root=root,
            test_command=tuple(test_command),
            exclude=tuple(exclude),
        )
    return workspaces


def load_config(
    path: str | Path | None = None, environ: Mapping[str, str] | None = None
) -> VerityConfig:
    """Parse ``verity.toml`` plus named env overrides into a frozen config.

    ``path`` defaults to the ``VERITY_CONFIG_PATH`` env variable, then
    ``./verity.toml``. A missing file yields contract defaults. Unknown
    keys, invalid values or non-loopback ``api_host`` raise
    ``VerityError("CONFIG_INVALID", ...)``.
    """
    env = os.environ if environ is None else environ
    if path is None:
        path = env.get("VERITY_CONFIG_PATH", "./verity.toml")
    config_path = Path(path)
    raw: dict[str, Any] = {}
    if config_path.exists():
        try:
            with open(config_path, "rb") as handle:
                raw = tomllib.load(handle)
        except tomllib.TOMLDecodeError as exc:
            raise _invalid(
                "verity.toml is not valid TOML", {"line": exc.lineno}
            ) from exc
    config_dir = config_path.resolve().parent

    unknown_top = set(raw) - _ALLOWED_KEYS - {"workspaces"}
    if unknown_top:
        raise _invalid(
            "verity.toml has unknown keys", {"unknown_keys": sorted(unknown_top)}
        )

    values = _parse_scalars(raw)
    for key in ("data_dir", "source_root", "database_path"):
        if key in values:
            values[key] = _resolve(config_dir, str(values[key]))
    workspaces = _parse_workspaces(raw, config_dir)

    return _apply_env(
        VerityConfig(
            **values,
            config_dir=config_dir,
            workspaces=workspaces,
            cline_provider_id=env.get("VERITY_CLINE_PROVIDER_ID") or None,
            cline_model_id=env.get("VERITY_CLINE_MODEL_ID") or None,
        ),
        env,
    )


def _apply_env(config: VerityConfig, env: Mapping[str, str]) -> VerityConfig:
    overrides: dict[str, Any] = {}
    if "VERITY_DATA_DIR" in env:
        overrides["data_dir"] = _resolve(config.config_dir, env["VERITY_DATA_DIR"])
    if "VERITY_SOURCE_ROOT" in env:
        overrides["source_root"] = _resolve(config.config_dir, env["VERITY_SOURCE_ROOT"])
    if "VERITY_DB_PATH" in env:
        overrides["database_path"] = _resolve(config.config_dir, env["VERITY_DB_PATH"])
    for env_name, field_name in (("VERITY_EMBEDDING_MODEL", "embedding_model"),
                                 ("VERITY_RERANKER_MODEL", "reranker_model")):
        if env_name in env:
            overrides[field_name] = env[env_name]
    if "VERITY_RERANKER_ENABLED" in env:
        if env["VERITY_RERANKER_ENABLED"] not in ("true", "false"):
            raise _invalid("VERITY_RERANKER_ENABLED must be true|false",
                           {"env": "VERITY_RERANKER_ENABLED"})
        overrides["reranker_enabled"] = env["VERITY_RERANKER_ENABLED"] == "true"
    if "VERITY_API_HOST" in env:
        if env["VERITY_API_HOST"] != "127.0.0.1":
            raise _invalid("VERITY_API_HOST must be 127.0.0.1 in v1",
                           {"env": "VERITY_API_HOST"})
        overrides["api_host"] = "127.0.0.1"
    if "VERITY_API_PORT" in env:
        try:
            port = int(env["VERITY_API_PORT"])
        except ValueError:
            raise _invalid("VERITY_API_PORT must be an integer",
                           {"env": "VERITY_API_PORT"}) from None
        if not 1 <= port <= 65535:
            raise _invalid("VERITY_API_PORT must be 1-65535",
                           {"env": "VERITY_API_PORT"})
        overrides["api_port"] = port
    if "VERITY_LOG_LEVEL" in env:
        level = env["VERITY_LOG_LEVEL"]
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            raise _invalid("VERITY_LOG_LEVEL must be DEBUG|INFO|WARNING|ERROR",
                           {"env": "VERITY_LOG_LEVEL"})
        overrides["log_level"] = level
    if not overrides:
        return config
    from dataclasses import replace

    return replace(config, **overrides)