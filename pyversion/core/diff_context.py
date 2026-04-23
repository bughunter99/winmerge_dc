from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.models import CompareStats, DiffList
from plugins.file_transform import FileTransformService
from plugins.plugin_manager import PluginManager


@dataclass
class DiffOptions:
    ignore_case: bool = False
    ignore_whitespace: bool = False
    recursive: bool = True
    # compare method: 'full' | 'quick' | 'date' | 'size' | 'date_size' | 'binary'
    compare_method: str = "full"


@dataclass
class DiffContext:
    """Python counterpart of WinMerge CDiffContext."""

    paths: list[Path]
    compare_mode: str
    options: DiffOptions = field(default_factory=DiffOptions)
    diff_list: DiffList = field(default_factory=DiffList)
    stats: CompareStats = field(default_factory=CompareStats)
    plugins_enabled: bool = True
    currently_hidden_items: list[str] = field(default_factory=list)
    plugin_manager: PluginManager = field(default_factory=PluginManager)
    file_transform: FileTransformService | None = None

    def __post_init__(self) -> None:
        if self.file_transform is None:
            self.file_transform = FileTransformService(self.plugin_manager)

    def swap(self, left_index: int, right_index: int) -> None:
        self.paths[left_index], self.paths[right_index] = self.paths[right_index], self.paths[left_index]
