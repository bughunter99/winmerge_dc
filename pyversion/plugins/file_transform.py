from __future__ import annotations

from pathlib import Path

from plugins.plugin_manager import PluginManager


class FileTransformService:
    """Counterpart of FileTransform pipeline entry."""

    def __init__(self, plugin_manager: PluginManager) -> None:
        self._plugin_manager = plugin_manager

    def apply_unpackers(self, path: str | Path) -> Path:
        source = path if isinstance(path, Path) else Path(path)
        return self._plugin_manager.apply_unpackers(source)

    def apply_prediff_text(self, text: str, source_path: str | Path) -> str:
        source = source_path if isinstance(source_path, Path) else Path(source_path)
        return self._plugin_manager.apply_prediff_text(text, source)
