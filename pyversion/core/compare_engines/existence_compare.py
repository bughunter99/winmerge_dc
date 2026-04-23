from __future__ import annotations

from pathlib import Path


class ExistenceCompareEngine:
    """Counterpart of ExistenceCompare."""

    def compare(self, left: Path, right: Path) -> int:
        return 0 if left.exists() and right.exists() else 1
