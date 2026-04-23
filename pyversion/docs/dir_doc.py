from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.diff_context import DiffContext
from core.diff_thread import DiffThreadController
from core.folder_scan import FolderScanResult, collect_file_pairs
from core.models import FilePairResult


class DirDocument(QObject):
    """Python counterpart of CDirDoc."""

    scan_ready = Signal()
    collect_completed = Signal(int)
    compare_progressed = Signal(int)
    compare_item_ready = Signal(object)  # emits FilePairResult
    compare_completed = Signal()
    failed = Signal(str)

    def __init__(self, diff_context: DiffContext) -> None:
        super().__init__()
        self.context = diff_context
        self.left_root: Path | None = None
        self.right_root: Path | None = None
        self.scan_result = FolderScanResult()
        self.results: list[FilePairResult] = []
        self._thread = DiffThreadController()
        self._thread.progressed.connect(self.compare_progressed.emit)
        self._thread.item_ready.connect(self._on_item_ready)
        self._thread.completed.connect(self.compare_completed.emit)
        self._thread.failed.connect(self.failed.emit)

    def init_compare(self, paths: list[Path]) -> None:
        if len(paths) < 2:
            self.failed.emit("Need at least two folders.")
            return
        self.left_root, self.right_root = paths[0], paths[1]
        if not self.left_root.is_dir() or not self.right_root.is_dir():
            self.failed.emit("Folder mode requires directory paths.")
            return

        self.scan_ready.emit()
        self._collect_phase()
        self._compare_phase()

    def _collect_phase(self) -> None:
        assert self.left_root is not None
        assert self.right_root is not None
        self.results = []
        self.scan_result = collect_file_pairs(

            self.left_root,
            self.right_root,
            recursive=self.context.options.recursive,
            hidden_items=set(self.context.currently_hidden_items),
        )
        self.context.stats.matched_pairs = len(self.scan_result.matched_pairs)
        self.context.stats.left_only_files = len(self.scan_result.left_only)
        self.context.stats.right_only_files = len(self.scan_result.right_only)
        self.collect_completed.emit(len(self.scan_result.matched_pairs))

    def _compare_phase(self) -> None:
        if not self.scan_result.matched_pairs:
            self.compare_completed.emit()
            return
        self._thread.start(self.context, self.scan_result.matched_pairs)

    def _on_item_ready(self, left: str, right: str, diff_count: int, status: str) -> None:
        result = FilePairResult(
            left=Path(left),
            right=Path(right),
            diff_count=diff_count,
            status=status,
        )
        self.results.append(result)
        self.compare_item_ready.emit(result)

    def abort_compare(self) -> None:
        self._thread.abort()

    def pause_compare(self) -> None:
        """Pause the background compare (CDirDoc::PauseCompare)."""
        self._thread.pause()

    def continue_compare(self) -> None:
        """Resume a paused compare (CDirDoc::ContinueCompare)."""
        self._thread.resume()

    def is_compare_paused(self) -> bool:
        return self._thread.is_paused()

    def is_compare_running(self) -> bool:
        return self._thread.is_running()

    def rescan(self, paths: list[Path] | None = None) -> None:
        """Re-run the full collect+compare pipeline (CDirDoc::Rescan)."""
        if paths is not None:
            self.left_root, self.right_root = paths[0], paths[1]
        if self.left_root is None or self.right_root is None:
            self.failed.emit("No folders set for rescan.")
            return
        self._thread.abort()
        self.results = []
        self._collect_phase()
        self._compare_phase()

    def refresh_selected(self, items: list[FilePairResult]) -> None:
        """Re-compare a subset of already-collected pairs (CDirDoc::RefreshSelectedItems)."""
        if not items:
            return
        pairs = [(r.left, r.right) for r in items]
        self._thread.abort()
        self._thread.start(self.context, pairs)
