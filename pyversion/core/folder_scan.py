from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FolderScanResult:
    matched_pairs: list[tuple[Path, Path]] = field(default_factory=list)
    left_only: list[Path] = field(default_factory=list)
    right_only: list[Path] = field(default_factory=list)


def _iter_relative_files(root: Path, recursive: bool) -> set[Path]:
    if recursive:
        return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}
    return {p.relative_to(root) for p in root.glob("*") if p.is_file()}


def collect_file_pairs(
    left_root: Path,
    right_root: Path,
    recursive: bool,
    hidden_items: set[str] | None = None,
) -> FolderScanResult:
    """Collect compare pairs by relative paths (collect phase)."""

    hidden_items = hidden_items or set()
    left_rel = _iter_relative_files(left_root, recursive)
    right_rel = _iter_relative_files(right_root, recursive)

    def is_hidden(rel_path: Path) -> bool:
        rel_text = rel_path.as_posix()
        return rel_text in hidden_items

    left_rel = {p for p in left_rel if not is_hidden(p)}
    right_rel = {p for p in right_rel if not is_hidden(p)}

    common = sorted(left_rel & right_rel)
    left_only = sorted(left_rel - right_rel)
    right_only = sorted(right_rel - left_rel)

    result = FolderScanResult()
    result.matched_pairs = [(left_root / rel, right_root / rel) for rel in common]
    result.left_only = [left_root / rel for rel in left_only]
    result.right_only = [right_root / rel for rel in right_only]
    return result
