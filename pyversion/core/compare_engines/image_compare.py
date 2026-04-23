from __future__ import annotations

from pathlib import Path


class ImageCompareEngine:
    """Placeholder counterpart of ImageCompare."""

    def compare(self, left: Path, right: Path) -> int:
        # Stage-1 placeholder: binary-equivalent check.
        return 0 if left.read_bytes() == right.read_bytes() else 1
