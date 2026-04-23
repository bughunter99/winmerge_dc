from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DiffItem:
    left_line: int
    right_line: int
    op: str
    left_text: str
    right_text: str


@dataclass
class DiffList:
    items: list[DiffItem] = field(default_factory=list)

    def add(self, item: DiffItem) -> None:
        self.items.append(item)

    def clear(self) -> None:
        self.items.clear()

    def count(self) -> int:
        return len(self.items)


@dataclass
class CompareStats:
    compared_files: int = 0
    different_files: int = 0
    identical_files: int = 0
    errors: int = 0
    matched_pairs: int = 0
    left_only_files: int = 0
    right_only_files: int = 0


@dataclass
class FilePair:
    left: Path
    right: Path


@dataclass
class FilePairResult:
    left: Path
    right: Path
    diff_count: int
    status: str  # "identical", "different", "error"
