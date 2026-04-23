from __future__ import annotations

from pathlib import Path
from typing import Protocol


class CompareEngine(Protocol):
    def compare(self, left: Path, right: Path) -> int:
        """Return number of differences."""
