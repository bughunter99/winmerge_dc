from __future__ import annotations

from pathlib import Path


class BinaryCompareEngine:
    """Rough counterpart of BinaryCompare/ByteCompare."""

    def compare(self, left: Path, right: Path) -> int:
        left_bytes = left.read_bytes()
        right_bytes = right.read_bytes()
        return 0 if left_bytes == right_bytes else 1
