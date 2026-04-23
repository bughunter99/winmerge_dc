from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QLabel, QProgressBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from docs.dir_doc import DirDocument
from core.models import FilePairResult


class DirViewWidget(QWidget):
    open_requested = Signal(object)  # emits list[Path]

    def __init__(self, document: DirDocument) -> None:
        super().__init__()
        self._doc = document
        self._status = QLabel("Folder compare ready")

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)

        # Result tree: Filename | Left path | Right path | Diffs | Status
        self._tree = QTreeWidget()
        self._tree.setColumnCount(5)
        self._tree.setHeaderLabels(["File", "Left", "Right", "Diffs", "Status"])
        self._tree.setAlternatingRowColors(True)
        self._tree.setSortingEnabled(True)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Folder compare view"))
        layout.addWidget(self._status)
        layout.addWidget(self._progress)
        layout.addWidget(self._tree, stretch=1)

        self._doc.scan_ready.connect(self._on_scan_ready)
        self._doc.collect_completed.connect(self._on_collect_completed)
        self._doc.compare_progressed.connect(self._on_compare_progressed)
        self._doc.compare_item_ready.connect(self._on_item_ready)
        self._doc.compare_completed.connect(self._on_compare_completed)
        self._doc.failed.connect(self._on_failed)

    def _on_scan_ready(self) -> None:
        self._tree.clear()
        self._status.setText("Folder roots accepted. Collecting file pairs...")

    def _on_collect_completed(self, pair_count: int) -> None:
        self._status.setText(f"Collect phase done. Matched pairs: {pair_count}")
        self._populate_side_only_items()

    def _on_compare_progressed(self, percent: int) -> None:
        self._progress.setValue(percent)

    def _on_item_ready(self, result: FilePairResult) -> None:
        item = QTreeWidgetItem([
            result.left.name,
            str(result.left),
            str(result.right),
            str(result.diff_count) if result.diff_count >= 0 else "—",
            result.status,
        ])
        item.setData(0, Qt.ItemDataRole.UserRole, [result.left, result.right])
        item.setToolTip(0, "Double-click to open file compare")
        if result.status == "different":
            item.setForeground(4, QColor(200, 100, 0))
        elif result.status == "error":
            item.setForeground(4, QColor(200, 0, 0))
        else:
            item.setForeground(4, QColor(0, 140, 0))
        self._tree.addTopLevelItem(item)
        for col in range(5):
            self._tree.resizeColumnToContents(col)

    def _on_compare_completed(self) -> None:
        stats = self._doc.context.stats
        self._status.setText(
            "Compare completed: "
            f"compared={stats.compared_files}, "
            f"different={stats.different_files}, "
            f"identical={stats.identical_files}, "
            f"errors={stats.errors}"
        )
        self._progress.setValue(100)

    def _on_failed(self, message: str) -> None:
        self._status.setText(f"Error: {message}")

    def _populate_side_only_items(self) -> None:
        for path in self._doc.scan_result.left_only:
            self._tree.addTopLevelItem(self._make_side_only_item(path, side="left"))
        for path in self._doc.scan_result.right_only:
            self._tree.addTopLevelItem(self._make_side_only_item(path, side="right"))
        for col in range(5):
            self._tree.resizeColumnToContents(col)

    def _make_side_only_item(self, path: Path, side: str) -> QTreeWidgetItem:
        if side == "left":
            values = [path.name, str(path), "", "—", "left-only"]
        else:
            values = [path.name, "", str(path), "—", "right-only"]
        item = QTreeWidgetItem(values)
        item.setForeground(4, QColor(90, 90, 180))
        item.setToolTip(0, "No matching file on the other side")
        return item

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        paths = item.data(0, Qt.ItemDataRole.UserRole)
        if not paths:
            return
        self.open_requested.emit(paths)
