from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.diff_context import DiffContext
from core.diff_wrapper import ThreeWayDiffSummary
from core.compare_engines.diffutils_engine import DiffUtilsEngine
from services.encoding_service import TextFileFormat, detect_text_format


class MergeDocument(QObject):
    """Python counterpart of CMergeDoc."""

    LEFT = 0
    MIDDLE = 1
    RIGHT = 2

    diff_ready = Signal(int)
    three_way_diff_ready = Signal(int, int, int)
    pane_texts_changed = Signal(str, str, str)
    blocks_updated = Signal(int, int)
    current_block_changed = Signal(int)  # emits current block index
    merge_applied = Signal(int, int, int)
    block_merge_applied = Signal(int, int, int, int)
    saved = Signal(int, str)
    modified_changed = Signal(bool)
    pane_metadata_changed = Signal(int)
    word_diffs_ready = Signal(int, int, list)  # pane_a, pane_b, list[opcodes per line]
    failed = Signal(str)

    def __init__(self, diff_context: DiffContext) -> None:
        super().__init__()
        self.context = diff_context
        self._engine = DiffUtilsEngine(diff_context)
        self.opened_paths: list[Path] = []
        self._pane_lines: dict[int, list[str]] = {}
        self._pane_formats: dict[int, TextFileFormat] = {}
        self._pane_read_only: dict[int, bool] = {}
        self._descriptions: dict[int, str] = {}
        self._disk_state: dict[int, tuple[int, int]] = {}
        self._dirty_panes: set[int] = set()
        self._blocks: list[MergeBlock] = []
        self._current_block: int = 0
        # Undo/redo stacks: per-pane list of line snapshots
        self._undo_stacks: dict[int, list[list[str]]] = {0: [], 1: [], 2: []}
        self._redo_stacks: dict[int, list[list[str]]] = {0: [], 1: [], 2: []}
        # Sync points: line index anchors shared across panes
        self._sync_points: list[int] = []

    def _reset_undo_redo(self) -> None:
        for p in (self.LEFT, self.MIDDLE, self.RIGHT):
            self._undo_stacks[p] = []
            self._redo_stacks[p] = []

    def open_docs(self, paths: list[Path]) -> None:
        self._reset_undo_redo()
        self.opened_paths = paths
        if len(paths) < 2:
            self.failed.emit("Need at least two files.")
            return
        try:
            if len(paths) == 2:
                self._pane_formats = {
                    self.LEFT: detect_text_format(paths[0]),
                    self.RIGHT: detect_text_format(paths[1]),
                }
                self._pane_read_only = {
                    self.LEFT: not os.access(paths[0], os.W_OK),
                    self.MIDDLE: True,
                    self.RIGHT: not os.access(paths[1], os.W_OK),
                }
                self._descriptions = {
                    self.LEFT: paths[0].name,
                    self.MIDDLE: "",
                    self.RIGHT: paths[1].name,
                }
                self._pane_lines = {
                    self.LEFT: self._engine.wrapper.load_processed_lines(paths[0]),
                    self.MIDDLE: [],
                    self.RIGHT: self._engine.wrapper.load_processed_lines(paths[1]),
                }
                self._record_disk_state(self.LEFT, paths[0])
                self._record_disk_state(self.RIGHT, paths[1])
                self._blocks = []
                diff_count = self._engine.compare(paths[0], paths[1])
                self.diff_ready.emit(diff_count)
                self._emit_pane_texts()
                self.modified_changed.emit(False)
                return
            if len(paths) == 3:
                self._pane_formats = {
                    self.LEFT: detect_text_format(paths[self.LEFT]),
                    self.MIDDLE: detect_text_format(paths[self.MIDDLE]),
                    self.RIGHT: detect_text_format(paths[self.RIGHT]),
                }
                self._pane_read_only = {
                    self.LEFT: not os.access(paths[self.LEFT], os.W_OK),
                    self.MIDDLE: not os.access(paths[self.MIDDLE], os.W_OK),
                    self.RIGHT: not os.access(paths[self.RIGHT], os.W_OK),
                }
                self._descriptions = {
                    self.LEFT: paths[self.LEFT].name,
                    self.MIDDLE: paths[self.MIDDLE].name,
                    self.RIGHT: paths[self.RIGHT].name,
                }
                self._pane_lines = {
                    self.LEFT: self._engine.wrapper.load_processed_lines(paths[self.LEFT]),
                    self.MIDDLE: self._engine.wrapper.load_processed_lines(paths[self.MIDDLE]),
                    self.RIGHT: self._engine.wrapper.load_processed_lines(paths[self.RIGHT]),
                }
                self._record_disk_state(self.LEFT, paths[self.LEFT])
                self._record_disk_state(self.MIDDLE, paths[self.MIDDLE])
                self._record_disk_state(self.RIGHT, paths[self.RIGHT])
                self._emit_three_way_summary_and_blocks(update_stats=True)
                self._emit_pane_texts()
                self.modified_changed.emit(False)
                return
            self.failed.emit("Text compare currently supports 2 or 3 files.")
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

    def is_three_way_mode(self) -> bool:
        return len(self.opened_paths) == 3 and len(self._pane_lines) == 3

    def get_pane_text(self, pane: int) -> str:
        return "\n".join(self._pane_lines.get(pane, []))

    def get_description(self, pane: int) -> str:
        return self._descriptions.get(pane, "")

    def set_description(self, pane: int, text: str) -> None:
        self._descriptions[pane] = text
        self.pane_metadata_changed.emit(pane)

    def get_pane_path(self, pane: int) -> Path | None:
        if not self.opened_paths:
            return None
        if self.is_three_way_mode():
            if pane in (self.LEFT, self.MIDDLE, self.RIGHT):
                return self.opened_paths[pane]
            return None
        if pane == self.LEFT and len(self.opened_paths) >= 1:
            return self.opened_paths[0]
        if pane == self.RIGHT and len(self.opened_paths) >= 2:
            return self.opened_paths[1]
        return None

    def _set_pane_path(self, pane: int, path: Path) -> None:
        if self.is_three_way_mode():
            if pane in (self.LEFT, self.MIDDLE, self.RIGHT):
                self.opened_paths[pane] = path
            return
        if pane == self.LEFT and len(self.opened_paths) >= 1:
            self.opened_paths[0] = path
        elif pane == self.RIGHT and len(self.opened_paths) >= 2:
            self.opened_paths[1] = path

    def can_save_pane(self, pane: int) -> bool:
        return self.get_pane_path(pane) is not None

    def get_read_only(self, pane: int) -> bool:
        return self._pane_read_only.get(pane, True)

    def set_read_only(self, pane: int, read_only: bool) -> None:
        self._pane_read_only[pane] = read_only
        self.pane_metadata_changed.emit(pane)

    def is_dirty(self, pane: int) -> bool:
        return pane in self._dirty_panes

    def is_modified(self) -> bool:
        return bool(self._dirty_panes)

    def get_modified_panes(self) -> list[int]:
        return sorted(self._dirty_panes)

    def get_pane_format(self, pane: int) -> TextFileFormat | None:
        return self._pane_formats.get(pane)

    def is_mixed_eol(self, pane: int) -> bool:
        fmt = self.get_pane_format(pane)
        return bool(fmt and fmt.mixed_eol)

    def check_pane_changed_on_disk(self, pane: int) -> bool:
        path = self.get_pane_path(pane)
        if path is None or not path.exists():
            return False
        current = self._get_disk_state(path)
        return current != self._disk_state.get(pane)

    def rescan_from_disk(self) -> bool:
        try:
            for pane in (self.LEFT, self.MIDDLE, self.RIGHT):
                path = self.get_pane_path(pane)
                if path is None or not path.exists():
                    continue
                self._pane_formats[pane] = detect_text_format(path)
                self._pane_lines[pane] = self._engine.wrapper.load_processed_lines(path)
                self._record_disk_state(pane, path)
                self._dirty_panes.discard(pane)

            if self.is_three_way_mode():
                self._emit_three_way_summary_and_blocks(update_stats=True)
            else:
                count = self._engine.compare(self.opened_paths[0], self.opened_paths[1])
                self.diff_ready.emit(count)
            self._emit_pane_texts()
            self.modified_changed.emit(False)
            return True
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return False

    def get_block_count(self) -> int:
        return len(self._blocks)

    def get_conflict_count(self) -> int:
        return sum(1 for block in self._blocks if block.is_conflict)

    def get_block(self, index: int) -> "MergeBlock":
        return self._blocks[index]

    def get_blocks_snapshot(self) -> list["MergeBlock"]:
        return list(self._blocks)

    @property
    def current_block(self) -> int:
        return self._current_block

    def navigate_block(self, delta: int) -> int:
        """Move current block by delta (-1 or +1). Returns new index."""
        if not self._blocks:
            return 0
        self._current_block = max(0, min(len(self._blocks) - 1, self._current_block + delta))
        self.current_block_changed.emit(self._current_block)
        return self._current_block

    def set_current_block(self, index: int) -> None:
        if not self._blocks:
            return
        self._current_block = max(0, min(len(self._blocks) - 1, index))
        self.current_block_changed.emit(self._current_block)

    def update_pane_text(self, pane: int, text: str) -> None:
        """Accept edited text from UI and store as pane lines (no re-compare yet).

        Pushes current state onto the undo stack before applying change.
        """
        if pane not in (self.LEFT, self.MIDDLE, self.RIGHT):
            self.failed.emit(f"Invalid pane index: {pane}")
            return
        # snapshot current state for undo (CMergeDoc::UndoGroup equivalent)
        current = list(self._pane_lines.get(pane, []))
        self._undo_stacks[pane].append(current)
        self._redo_stacks[pane].clear()
        self._pane_lines[pane] = text.splitlines()
        self._dirty_panes.add(pane)
        self.modified_changed.emit(True)

    def can_undo(self, pane: int) -> bool:
        """Return True if there is an undo step available for this pane."""
        return bool(self._undo_stacks.get(pane))

    def can_redo(self, pane: int) -> bool:
        """Return True if there is a redo step available for this pane."""
        return bool(self._redo_stacks.get(pane))

    def undo(self, pane: int) -> bool:
        """Restore previous pane content (CMergeDoc::Undo equivalent)."""
        if not self.can_undo(pane):
            return False
        current = list(self._pane_lines.get(pane, []))
        self._redo_stacks[pane].append(current)
        self._pane_lines[pane] = self._undo_stacks[pane].pop()
        # mark dirty unless we're back to pristine state
        if self._undo_stacks[pane]:
            self._dirty_panes.add(pane)
        else:
            self._dirty_panes.discard(pane)
        self.modified_changed.emit(self.is_modified())
        self._emit_pane_texts()
        return True

    def redo(self, pane: int) -> bool:
        """Re-apply undone pane content (CMergeDoc::Redo equivalent)."""
        if not self.can_redo(pane):
            return False
        current = list(self._pane_lines.get(pane, []))
        self._undo_stacks[pane].append(current)
        self._pane_lines[pane] = self._redo_stacks[pane].pop()
        self._dirty_panes.add(pane)
        self.modified_changed.emit(True)
        self._emit_pane_texts()
        return True

    def clear_undo_redo(self, pane: int | None = None) -> None:
        """Clear all undo/redo history, optionally for a single pane."""
        panes = (self.LEFT, self.MIDDLE, self.RIGHT) if pane is None else (pane,)
        for p in panes:
            self._undo_stacks[p] = []
            self._redo_stacks[p] = []

    # ------------------------------------------------------------------
    # Sync points (CMergeDoc sync-point mechanism)
    # ------------------------------------------------------------------

    def add_sync_point(self, line_index: int) -> None:
        """Add a sync point at the given 0-based line index (all panes share the anchor)."""
        if line_index not in self._sync_points:
            self._sync_points.append(line_index)
            self._sync_points.sort()

    def remove_sync_point(self, line_index: int) -> bool:
        """Remove a sync point. Returns True if it existed."""
        if line_index in self._sync_points:
            self._sync_points.remove(line_index)
            return True
        return False

    def clear_sync_points(self) -> None:
        """Clear all sync points."""
        self._sync_points.clear()

    def get_sync_points(self) -> list[int]:
        """Return a copy of the sync point line indices (sorted ascending)."""
        return list(self._sync_points)

    def navigate_to_sync_point(self, index: int) -> int | None:
        """Return the line index of the nth sync point, or None if index out of range."""
        if 0 <= index < len(self._sync_points):
            return self._sync_points[index]
        return None

    def save_pane(self, pane: int) -> bool:
        path = self.get_pane_path(pane)
        if path is None:
            self.failed.emit("Selected pane has no backing file path.")
            return False
        if self.get_read_only(pane):
            self.failed.emit("Selected pane is read-only.")
            return False
        try:
            text = self.get_pane_text(pane)
            fmt = self._pane_formats.get(pane, TextFileFormat(encoding="utf-8", newline="\n"))
            if text:
                normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
                payload = normalized_text.replace("\n", fmt.newline) + fmt.newline
            else:
                payload = ""
            path.write_text(payload, encoding=fmt.encoding, newline="")
            self._dirty_panes.discard(pane)
            self._record_disk_state(pane, path)
            self.saved.emit(pane, str(path))
            self.modified_changed.emit(self.is_modified())
            return True
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
            return False

    def save_pane_as(self, pane: int, target_path: Path) -> bool:
        if pane not in self._pane_lines:
            self.failed.emit("Invalid pane index.")
            return False
        original_path = self.get_pane_path(pane)
        original_format = self._pane_formats.get(pane, TextFileFormat(encoding="utf-8", newline="\n"))
        try:
            self._set_pane_path(pane, target_path)
            self._pane_formats[pane] = original_format
            self._pane_read_only[pane] = False
            self._descriptions[pane] = target_path.name
            ok = self.save_pane(pane)
            if ok:
                self.pane_metadata_changed.emit(pane)
                return True
        finally:
            if not target_path.exists() and original_path is not None and self.get_pane_path(pane) == target_path:
                self._set_pane_path(pane, original_path)
                self._pane_formats[pane] = original_format
        return False

    def save_all(self) -> int:
        saved_count = 0
        for pane in (self.LEFT, self.MIDDLE, self.RIGHT):
            if pane not in self._dirty_panes:
                continue
            if self.save_pane(pane):
                saved_count += 1
        return saved_count

    def _get_disk_state(self, path: Path) -> tuple[int, int]:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size

    def _record_disk_state(self, pane: int, path: Path) -> None:
        self._disk_state[pane] = self._get_disk_state(path)

    def recompare(self) -> None:
        """Re-run diff on current in-memory pane contents and refresh blocks/signals."""
        try:
            if self.is_three_way_mode():
                self._emit_three_way_summary_and_blocks(update_stats=False)
                self._emit_pane_texts()
            else:
                # 2-way: compare LEFT vs RIGHT pane contents
                left = self._pane_lines.get(self.LEFT, [])
                right = self._pane_lines.get(self.RIGHT, [])
                wrapper = self._engine.wrapper
                count = wrapper._count_diff_from_lines(left, right, reset_diff_list=True, update_stats=True)
                self.diff_ready.emit(count)
                self._emit_pane_texts()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))

    def apply_merge_copy(self, src_pane: int, dst_pane: int) -> bool:
        if not self.is_three_way_mode():
            self.failed.emit("Merge action requires 3-way mode.")
            return False
        if src_pane == dst_pane:
            self.failed.emit("Source and destination panes must be different.")
            return False
        if src_pane not in self._pane_lines or dst_pane not in self._pane_lines:
            self.failed.emit("Invalid pane index.")
            return False

        self._pane_lines[dst_pane] = list(self._pane_lines[src_pane])
        self._dirty_panes.add(dst_pane)

        summary = self._emit_three_way_summary_and_blocks(update_stats=False)
        self._emit_pane_texts()
        self.merge_applied.emit(src_pane, dst_pane, summary.total_diffs)
        return True

    def get_word_diffs_for_lines(
        self,
        pane_a: int,
        pane_b: int,
        line_indices: list[int] | None = None,
    ) -> list[list[tuple[str, int, int, int, int]]]:
        """Return word-level (character) opcodes for each line pair between two panes.

        Corresponds to CDiffTextBuffer::GetWordDiffArray / ShowLineDiff.
        Returns one opcode list per line.  Emits word_diffs_ready signal.
        """
        lines_a = self._pane_lines.get(pane_a, [])
        lines_b = self._pane_lines.get(pane_b, [])
        matched_count = min(len(lines_a), len(lines_b))
        indices = line_indices if line_indices is not None else list(range(matched_count))
        wrapper = self._engine.wrapper
        result: list[list[tuple[str, int, int, int, int]]] = []
        for idx in indices:
            la = lines_a[idx] if idx < len(lines_a) else ""
            lb = lines_b[idx] if idx < len(lines_b) else ""
            result.append(wrapper.get_word_diff_array(la, lb))
        self.word_diffs_ready.emit(pane_a, pane_b, result)  # type: ignore[arg-type]
        return result

    def apply_merge_lines(
        self,
        src_pane: int,
        dst_pane: int,
        first_line: int,
        last_line: int,
    ) -> bool:
        """Copy a range of lines [first_line, last_line) from src_pane to dst_pane.

        Corresponds to CMergeDoc::CopyMultipleList / LineListCopy.
        """
        if src_pane == dst_pane:
            self.failed.emit("Source and destination panes must be different.")
            return False
        if src_pane not in self._pane_lines or dst_pane not in self._pane_lines:
            self.failed.emit("Invalid pane index.")
            return False
        if first_line < 0 or last_line < first_line:
            self.failed.emit("Invalid line range.")
            return False
        src_lines = self._pane_lines[src_pane]
        clamped_start = min(first_line, len(src_lines))
        clamped_end = min(last_line, len(src_lines))
        src_slice = list(src_lines[clamped_start:clamped_end])

        dst_lines = self._pane_lines[dst_pane]
        dst_clamped_start = min(first_line, len(dst_lines))
        dst_clamped_end = min(last_line, len(dst_lines))
        self._pane_lines[dst_pane][dst_clamped_start:dst_clamped_end] = src_slice
        self._dirty_panes.add(dst_pane)

        if self.is_three_way_mode():
            summary = self._emit_three_way_summary_and_blocks(update_stats=False)
            self._emit_pane_texts()
            self.merge_applied.emit(src_pane, dst_pane, summary.total_diffs)
        else:
            left = self._pane_lines.get(self.LEFT, [])
            right = self._pane_lines.get(self.RIGHT, [])
            count = self._engine.wrapper._count_diff_from_lines(
                left, right, reset_diff_list=True, update_stats=False
            )
            self.diff_ready.emit(count)
            self._emit_pane_texts()
        return True

    def apply_merge_block(self, src_pane: int, dst_pane: int, block_index: int) -> bool:
        if not self.is_three_way_mode():
            self.failed.emit("Block merge action requires 3-way mode.")
            return False
        if src_pane == dst_pane:
            self.failed.emit("Source and destination panes must be different.")
            return False
        if not (0 <= block_index < len(self._blocks)):
            self.failed.emit("Invalid block index.")
            return False

        block = self._blocks[block_index]
        src_start, src_end = block.ranges[src_pane]
        dst_start, dst_end = block.ranges[dst_pane]

        src_slice = list(self._pane_lines[src_pane][src_start:src_end])
        self._pane_lines[dst_pane][dst_start:dst_end] = src_slice
        self._dirty_panes.add(dst_pane)

        summary = self._emit_three_way_summary_and_blocks(update_stats=False)
        self._emit_pane_texts()
        self.block_merge_applied.emit(block_index, src_pane, dst_pane, summary.total_diffs)
        return True

    def _emit_pane_texts(self) -> None:
        self.pane_texts_changed.emit(
            self.get_pane_text(self.LEFT),
            self.get_pane_text(self.MIDDLE),
            self.get_pane_text(self.RIGHT),
        )

    def _emit_three_way_summary_and_blocks(self, update_stats: bool) -> ThreeWayDiffSummary:
        if update_stats:
            summary = self._engine.wrapper.run_three_way_diff(
                self.opened_paths[self.LEFT],
                self.opened_paths[self.MIDDLE],
                self.opened_paths[self.RIGHT],
            )
        else:
            summary = self._engine.wrapper.run_three_way_diff_from_lines(
                self._pane_lines[self.LEFT],
                self._pane_lines[self.MIDDLE],
                self._pane_lines[self.RIGHT],
            )

        self.three_way_diff_ready.emit(
            summary.left_middle_diffs,
            summary.middle_right_diffs,
            summary.total_diffs,
        )
        self._rebuild_blocks()
        self._current_block = max(0, min(self._current_block, len(self._blocks) - 1))
        self.blocks_updated.emit(self.get_block_count(), self.get_conflict_count())
        return summary

    def _rebuild_blocks(self) -> None:
        left_lines = self._pane_lines[self.LEFT]
        middle_lines = self._pane_lines[self.MIDDLE]
        right_lines = self._pane_lines[self.RIGHT]
        lm_ops = self._engine.wrapper.build_opcodes_from_lines(left_lines, middle_lines)
        mr_ops = self._engine.wrapper.build_opcodes_from_lines(middle_lines, right_lines)

        middle_ranges: list[tuple[int, int]] = []
        for op, _i1, _i2, j1, j2 in lm_ops:
            if op != "equal":
                middle_ranges.append((j1, j2))
        for op, i1, i2, _j1, _j2 in mr_ops:
            if op != "equal":
                middle_ranges.append((i1, i2))

        merged_middle_ranges = _merge_ranges(middle_ranges)
        blocks: list[MergeBlock] = []
        for idx, middle_range in enumerate(merged_middle_ranges):
            left_range = _map_middle_to_other(lm_ops, middle_range, middle_on_right=True)
            right_range = _map_middle_to_other(mr_ops, middle_range, middle_on_right=False)

            left_slice = left_lines[left_range[0]:left_range[1]]
            middle_slice = middle_lines[middle_range[0]:middle_range[1]]
            right_slice = right_lines[right_range[0]:right_range[1]]

            left_changed = left_slice != middle_slice
            right_changed = right_slice != middle_slice
            is_conflict = left_changed and right_changed and left_slice != right_slice
            kind = "conflict" if is_conflict else "change"

            blocks.append(
                MergeBlock(
                    index=idx,
                    ranges={
                        self.LEFT: left_range,
                        self.MIDDLE: middle_range,
                        self.RIGHT: right_range,
                    },
                    is_conflict=is_conflict,
                    kind=kind,
                )
            )
        self._blocks = blocks


@dataclass
class MergeBlock:
    index: int
    ranges: dict[int, tuple[int, int]]
    is_conflict: bool
    kind: str


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not ranges:
        return []
    sorted_ranges = sorted(ranges, key=lambda it: (it[0], it[1]))
    merged: list[tuple[int, int]] = [sorted_ranges[0]]
    for start, end in sorted_ranges[1:]:
        cur_start, cur_end = merged[-1]
        if start <= cur_end:
            merged[-1] = (cur_start, max(cur_end, end))
        else:
            merged.append((start, end))
    return merged


def _map_middle_to_other(
    opcodes: list[tuple[str, int, int, int, int]],
    middle_range: tuple[int, int],
    middle_on_right: bool,
) -> tuple[int, int]:
    m_start, m_end = middle_range
    mapped: list[tuple[int, int]] = []

    for op, i1, i2, j1, j2 in opcodes:
        if middle_on_right:
            o1, o2, m1, m2 = i1, i2, j1, j2
        else:
            o1, o2, m1, m2 = j1, j2, i1, i2

        overlaps = not (m_end <= m1 or m_start >= m2)
        if not overlaps:
            continue

        if op == "equal":
            ov_start = max(m_start, m1)
            ov_end = min(m_end, m2)
            mapped.append((o1 + (ov_start - m1), o1 + (ov_end - m1)))
        else:
            mapped.append((o1, o2))

    if mapped:
        return min(a for a, _ in mapped), max(b for _, b in mapped)

    # Fallback insertion-point mapping.
    for _op, i1, _i2, j1, _j2 in opcodes:
        if middle_on_right and j1 >= m_start:
            return i1, i1
        if not middle_on_right and i1 >= m_start:
            return j1, j1
    return 0, 0
