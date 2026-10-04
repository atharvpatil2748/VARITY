"""VERITY command-line interface.

Phase 9 structure (``verity/cli.py``): ``ingest``, ``search``, ``serve``
and ``demo`` commands. The CLI is a thin adapter over ``VerityService``
and never touches storage directly.
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    """Build the v1 CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="verity",
        description="VERITY - Your documents. Your specs. Evidence that Cline can cite.",
    )
    parser.add_argument("--config", default="./verity.toml", help="verity.toml path")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ingest", help="Ingest documents from the configured source root")
    sub.add_parser("search", help="Search evidence for a query")
    sub.add_parser("serve", help="Run the MCP stdio server for external Cline clients")
    sub.add_parser("demo", help="Run the eight-hour demo slice end to end")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Skeleton for Phase 11; commands land with the service."""
    args = build_parser().parse_args(argv)
    print(
        f"verity {args.command!r} is scheduled for Phase 11 "
        "(see Docs/ARCHITECTURE.md and Docs/contracts/09).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())