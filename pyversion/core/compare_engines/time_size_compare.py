from __future__ import annotations

from pathlib import Path


class TimeSizeCompareEngine:
    """Counterpart of TimeSizeCompare."""

    def compare(self, left: Path, right: Path) -> int:
        lstat = left.stat()
        rstat = right.stat()
        same_size = lstat.st_size == rstat.st_size
        same_mtime = int(lstat.st_mtime) == int(rstat.st_mtime)
        return 0 if same_size and same_mtime else 1
