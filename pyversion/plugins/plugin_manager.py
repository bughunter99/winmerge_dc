from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from pathlib import Path
from typing import Any


class PluginManager:
    """Counterpart of WinMerge PluginManager."""

    def __init__(self) -> None:
        self._pipelines: dict[str, list[Callable[..., Any]]] = defaultdict(list)

    def register(self, event_name: str, callback: Callable[..., Any]) -> None:
        self._pipelines[event_name].append(callback)

    def get_pipeline(self, event_name: str) -> list[str]:
        return [cb.__name__ for cb in self._pipelines.get(event_name, [])]

    def apply_unpackers(self, path: Path) -> Path:
        current = path
        for callback in self._pipelines.get("unpacker", []):
            result = callback(current)
            if isinstance(result, Path):
                current = result
            elif isinstance(result, str):
                current = Path(result)
        return current

    def apply_prediff_text(self, text: str, source_path: Path) -> str:
        current = text
        for callback in self._pipelines.get("prediff", []):
            result = callback(current, source_path)
            if isinstance(result, str):
                current = result
        return current
