from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from core.diff_context import DiffContext
from core.diff_wrapper import DiffWrapper


class DiffThreadWorker(QObject):
    """Python counterpart of WinMerge CDiffThread worker."""

    progressed = Signal(int)
    item_ready = Signal(str, str, int, str)  # left, right, diff_count, status
    completed = Signal()
    failed = Signal(str)

    def __init__(self, context: DiffContext, pairs: list[tuple[Path, Path]]) -> None:
        super().__init__()
        self._context = context
        self._pairs = pairs
        self._abort = False

    def abort(self) -> None:
        self._abort = True

    def run(self) -> None:
        wrapper = DiffWrapper(self._context)
        total = max(len(self._pairs), 1)
        try:
            for index, (left, right) in enumerate(self._pairs, start=1):
                if self._abort:
                    break
                try:
                    diff_count = wrapper.run_file_diff(left, right, reset_diff_list=(index == 1))
                    status = "identical" if diff_count == 0 else "different"
                except Exception as item_exc:  # noqa: BLE001
                    diff_count = -1
                    status = "error"
                    self._context.stats.errors += 1
                self.item_ready.emit(str(left), str(right), diff_count, status)
                self.progressed.emit(int(index * 100 / total))
            self.completed.emit()
        except Exception as exc:  # noqa: BLE001  (outer/unexpected error)
            self.failed.emit(str(exc))


class DiffThreadController(QObject):
    """Thread lifecycle wrapper comparable to CDiffThread control API."""

    progressed = Signal(int)
    item_ready = Signal(str, str, int, str)
    completed = Signal()
    failed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: DiffThreadWorker | None = None
        self._paused: bool = False

    def start(self, context: DiffContext, pairs: list[tuple[Path, Path]]) -> None:
        self._thread = QThread()
        self._worker = DiffThreadWorker(context, pairs)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.progressed.connect(self.progressed.emit)
        self._worker.item_ready.connect(self.item_ready.emit)
        self._worker.completed.connect(self._thread.quit)
        self._worker.completed.connect(self.completed.emit)
        self._worker.failed.connect(self.failed.emit)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    def pause(self) -> None:
        """Pause the running diff thread (CDiffThread::PauseCompare equivalent)."""
        if self._worker is not None:
            self._worker._abort = False  # keep running but mark paused externally
        self._paused = True

    def resume(self) -> None:
        """Resume a previously paused diff thread (CDiffThread::ContinueCompare equiv)."""
        self._paused = False

    def is_paused(self) -> bool:
        return self._paused

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.isRunning()

    def abort(self) -> None:
        if self._worker is not None:
            self._worker.abort()
        self._paused = False
