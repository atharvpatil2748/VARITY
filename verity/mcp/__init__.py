"""VERITY MCP subpackage.

Phase 9 structure: stdio MCP server for external Cline clients (contract
09). Owner Vandit. Handlers contain no business logic; every tool call
delegates to ``VerityService``.
"""

__all__ = ["build_server"]