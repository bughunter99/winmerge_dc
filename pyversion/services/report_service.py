from __future__ import annotations

from core.diff_context import DiffContext


def build_summary(context: DiffContext) -> str:
    stats = context.stats
    return (
        f"Compared: {stats.compared_files}, "
        f"Different: {stats.different_files}, "
        f"Identical: {stats.identical_files}, "
        f"Errors: {stats.errors}"
    )
