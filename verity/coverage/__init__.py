"""VERITY coverage subpackage.

Phase 9 structure: workspace safety/snapshot, candidate code/test search
and the evidence-backed evaluator (contract 12). Owner Vanashree.
"""

from .workspace import resolve_workspace_root

__all__ = ["resolve_workspace_root"]