from __future__ import annotations

from pathlib import Path

from core.diff_context import DiffContext
from core.diff_wrapper import DiffWrapper


class DiffUtilsEngine:
    """Python counterpart of CompareEngines::DiffUtils."""

    def __init__(self, context: DiffContext) -> None:
        self._wrapper = DiffWrapper(context)

    @property
    def wrapper(self) -> DiffWrapper:
        return self._wrapper

    def compare(self, left: Path, right: Path) -> int:
        return self._wrapper.run_file_diff(left, right)
