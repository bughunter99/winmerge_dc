from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from core.diff_context import DiffContext
from core.models import DiffItem


Opcode: TypeAlias = tuple[str, int, int, int, int]


@dataclass
class ThreeWayDiffSummary:
    left_middle_diffs: int
    middle_right_diffs: int

    @property
    def total_diffs(self) -> int:
        return self.left_middle_diffs + self.middle_right_diffs


class DiffWrapper:
    """Python counterpart of WinMerge CDiffWrapper."""

    def __init__(self, context: DiffContext) -> None:
        self.context = context

    def _load_lines(self, path: Path) -> list[str]:
        source_path = path
        if self.context.plugins_enabled and self.context.file_transform is not None:
            source_path = self.context.file_transform.apply_unpackers(path)

        text = source_path.read_text(encoding="utf-8", errors="replace")
        if self.context.plugins_enabled and self.context.file_transform is not None:
            text = self.context.file_transform.apply_prediff_text(text, source_path)
        return text.splitlines()

    def _normalize_line(self, line: str) -> str:
        result = line
        if self.context.options.ignore_whitespace:
            result = " ".join(result.split())
        if self.context.options.ignore_case:
            result = result.casefold()
        return result

    def load_processed_lines(self, path: Path) -> list[str]:
        return self._load_lines(path)

    def build_opcodes_from_lines(self, left_lines: list[str], right_lines: list[str]) -> list[Opcode]:
        left_norm = [self._normalize_line(line) for line in left_lines]
        right_norm = [self._normalize_line(line) for line in right_lines]
        matcher = difflib.SequenceMatcher(a=left_norm, b=right_norm, autojunk=False)
        return list(matcher.get_opcodes())

    def build_opcodes_from_paths(self, left: Path, right: Path) -> list[Opcode]:
        return self.build_opcodes_from_lines(self._load_lines(left), self._load_lines(right))

    def _count_diff_from_lines(
        self,
        left_lines: list[str],
        right_lines: list[str],
        reset_diff_list: bool,
        update_stats: bool,
    ) -> int:
        if reset_diff_list:
            self.context.diff_list.clear()

        matcher = difflib.SequenceMatcher(
            a=[self._normalize_line(line) for line in left_lines],
            b=[self._normalize_line(line) for line in right_lines],
            autojunk=False,
        )
        diff_count = 0
        for op, i1, i2, j1, j2 in matcher.get_opcodes():
            if op == "equal":
                continue
            diff_count += 1
            self.context.diff_list.add(
                DiffItem(
                    left_line=i1 + 1,
                    right_line=j1 + 1,
                    op=op,
                    left_text="\n".join(left_lines[i1:i2]),
                    right_text="\n".join(right_lines[j1:j2]),
                )
            )

        if update_stats:
            self.context.stats.compared_files += 1
            if diff_count == 0:
                self.context.stats.identical_files += 1
            else:
                self.context.stats.different_files += 1
        return diff_count

    def run_file_diff(self, left: Path, right: Path, reset_diff_list: bool = True) -> int:
        """Dispatch to the appropriate comparison engine based on options.compare_method.

        - 'quick'      : only check file sizes (fast but imprecise)
        - 'date'       : compare modification timestamps only
        - 'size'       : compare file sizes only  
        - 'date_size'  : compare date AND size
        - 'binary'     : byte-by-byte comparison
        - 'full'       : full line-by-line text diff (default)
        """
        method = self.context.options.compare_method
        if method == "size":
            return self._diff_by_size(left, right)
        if method == "date":
            return self._diff_by_date(left, right)
        if method == "date_size":
            return self._diff_by_date(left, right) or self._diff_by_size(left, right)
        if method == "quick":
            return self._diff_by_size(left, right)
        if method == "binary":
            return self._diff_binary(left, right, reset_diff_list)
        # default: full text diff
        left_lines = self._load_lines(left)
        right_lines = self._load_lines(right)
        return self._count_diff_from_lines(
            left_lines,
            right_lines,
            reset_diff_list=reset_diff_list,
            update_stats=True,
        )

    def _diff_by_size(self, left: Path, right: Path) -> int:
        """Return 0 if sizes match, 1 otherwise."""
        size_match = left.stat().st_size == right.stat().st_size
        if self.context.options.compare_method in ("size", "quick"):
            if size_match:
                self.context.stats.identical_files += 1
            else:
                self.context.stats.different_files += 1
        return 0 if size_match else 1

    def _diff_by_date(self, left: Path, right: Path) -> int:
        """Return 0 if modification times are identical (to-the-second), 1 otherwise."""
        # Compare integer seconds to ignore sub-second differences across filesystems
        lt = int(left.stat().st_mtime)
        rt = int(right.stat().st_mtime)
        same = lt == rt
        self.context.stats.compared_files += 1
        if same:
            self.context.stats.identical_files += 1
        else:
            self.context.stats.different_files += 1
        return 0 if same else 1

    def _diff_binary(self, left: Path, right: Path, reset_diff_list: bool) -> int:
        """Byte-by-byte binary comparison.  Returns 0 (same) or 1 (different)."""
        if reset_diff_list:
            self.context.diff_list.clear()
        self.context.stats.compared_files += 1
        same = left.read_bytes() == right.read_bytes()
        if same:
            self.context.stats.identical_files += 1
        else:
            self.context.stats.different_files += 1
        return 0 if same else 1

    def run_three_way_diff(self, left: Path, middle: Path, right: Path) -> ThreeWayDiffSummary:
        """Run two 2-way comparisons to preserve WinMerge-style 3-pane topology."""

        left_lines = self._load_lines(left)
        middle_lines = self._load_lines(middle)
        right_lines = self._load_lines(right)
        left_middle = self._count_diff_from_lines(
            left_lines,
            middle_lines,
            reset_diff_list=True,
            update_stats=True,
        )
        middle_right = self._count_diff_from_lines(
            middle_lines,
            right_lines,
            reset_diff_list=False,
            update_stats=True,
        )
        return ThreeWayDiffSummary(
            left_middle_diffs=left_middle,
            middle_right_diffs=middle_right,
        )

    def get_word_diff_array(
        self, left_line: str, right_line: str
    ) -> list[tuple[str, int, int, int, int]]:
        """Return character-level opcodes between two lines (GetWordDiffArray equivalent).

        Each tuple is (op, left_start, left_end, right_start, right_end) using
        the same format as difflib SequenceMatcher.get_opcodes().
        """
        left_chars = list(left_line)
        right_chars = list(right_line)
        if self.context.options.ignore_case:
            left_norm = [c.casefold() for c in left_chars]
            right_norm = [c.casefold() for c in right_chars]
        else:
            left_norm = left_chars
            right_norm = right_chars
        matcher = difflib.SequenceMatcher(a=left_norm, b=right_norm, autojunk=False)
        return list(matcher.get_opcodes())

    def run_three_way_diff_from_lines(
        self,
        left_lines: list[str],
        middle_lines: list[str],
        right_lines: list[str],
    ) -> ThreeWayDiffSummary:
        """Run 3-way diff from in-memory buffers used after merge actions."""

        left_middle = self._count_diff_from_lines(
            left_lines,
            middle_lines,
            reset_diff_list=True,
            update_stats=False,
        )
        middle_right = self._count_diff_from_lines(
            middle_lines,
            right_lines,
            reset_diff_list=False,
            update_stats=False,
        )
        return ThreeWayDiffSummary(
            left_middle_diffs=left_middle,
            middle_right_diffs=middle_right,
        )
