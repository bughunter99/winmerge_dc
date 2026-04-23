from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from PySide6.QtCore import Slot
from PySide6.QtGui import QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QWidget,
)

from core.diff_context import DiffContext
from docs.dir_doc import DirDocument
from docs.merge_doc import MergeDocument
from ui.merge_views import MergeViewWidget
from ui.dir_views import DirViewWidget


@dataclass
class OpenRequest:
    paths: list[Path]
    mode: str = "auto"
    descriptions: list[str] = field(default_factory=list)


# ??????????????????????????????????????????????????????????????????????????????
# DocumentTab: pairs a doc with its view widget
# ??????????????????????????????????????????????????????????????????????????????

class _DocTab:
    """Lightweight envelope binding a document to its view widget."""

    def __init__(
        self,
        doc: MergeDocument | DirDocument,
        view: QWidget,
        title: str,
    ) -> None:
        self.doc = doc
        self.view = view
        self.title = title


# ??????????????????????????????????????????????????????????????????????????????

class MainWindow(QMainWindow):
    """Python counterpart of WinMerge CMainFrame.

    Supports multiple simultaneously open comparisons via a QTabWidget (MDI
    equivalent), diff navigation, and extended open routing (conflict files,
    clipboard content).
    """

    def __init__(self, app_config: object) -> None:
        super().__init__()
        self._app_config = app_config
        self.setWindowTitle("WinMerge")
        self.resize(1280, 800)

        # MDI-style tab container
        self._tab_widget = QTabWidget()
        self._tab_widget.setTabsClosable(True)
        self._tab_widget.setMovable(True)
        self._tab_widget.tabCloseRequested.connect(self._on_tab_close_requested)
        self._tab_widget.currentChanged.connect(self._on_tab_changed)
        self.setCentralWidget(self._tab_widget)

        self._docs: list[_DocTab] = []  # parallel to tab indices
        self._window_menu_actions: list = []

        self._wire_actions()

    # Menu construction

    def _wire_actions(self) -> None:
        # FILE
        file_menu = self.menuBar().addMenu("&File")
        open_action = file_menu.addAction("Open...")
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_dialog)

        open_conflict_action = file_menu.addAction("Open Conflict File...")
        open_conflict_action.triggered.connect(self._on_open_conflict_dialog)

        open_clipboard_action = file_menu.addAction("Open Clipboard Compare...")
        open_clipboard_action.triggered.connect(self._on_open_clipboard)

        file_menu.addSeparator()

        save_all_action = file_menu.addAction("Save All Dirty")
        save_all_shortcut = getattr(QKeySequence.StandardKey, "SaveAll", None)
        save_all_action.setShortcut(save_all_shortcut or QKeySequence("Ctrl+Shift+S"))
        save_all_action.triggered.connect(self._on_save_all_dirty)

        save_left_action = file_menu.addAction("Save Left")
        save_left_action.triggered.connect(lambda: self._on_save_pane(MergeDocument.LEFT))

        save_middle_action = file_menu.addAction("Save Middle")
        save_middle_action.triggered.connect(lambda: self._on_save_pane(MergeDocument.MIDDLE))

        save_right_action = file_menu.addAction("Save Right")
        save_right_action.triggered.connect(lambda: self._on_save_pane(MergeDocument.RIGHT))

        save_primary_action = file_menu.addAction("Save Primary")
        save_primary_action.setShortcut(QKeySequence.StandardKey.Save)
        save_primary_action.triggered.connect(self._on_save_primary)

        save_primary_as_action = file_menu.addAction("Save Primary As...")
        save_primary_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_primary_as_action.triggered.connect(self._on_save_primary_as)

        file_menu.addSeparator()

        close_action = file_menu.addAction("Close")
        close_action.setShortcut(QKeySequence.StandardKey.Close)
        close_action.triggered.connect(self._on_close_current_tab)

        rescan_action = file_menu.addAction("Rescan From Disk")
        rescan_action.triggered.connect(self._on_rescan_from_disk)

        # EDIT
        edit_menu = self.menuBar().addMenu("&Edit")
        undo_action = edit_menu.addAction("Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self._on_undo)
        redo_action = edit_menu.addAction("Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self._on_redo)

        # VIEW / NAVIGATE
        view_menu = self.menuBar().addMenu("&View")
        view_rescan_action = view_menu.addAction("Rescan")
        view_rescan_action.triggered.connect(self._on_rescan_from_disk)

        # MERGE / NAVIGATE
        merge_menu = self.menuBar().addMenu("&Merge")
        merge_prev_action = merge_menu.addAction("Previous Difference")
        merge_prev_action.setShortcut(QKeySequence("Alt+Up"))
        merge_prev_action.triggered.connect(self._on_navigate_prev)
        merge_next_action = merge_menu.addAction("Next Difference")
        merge_next_action.setShortcut(QKeySequence("Alt+Down"))
        merge_next_action.triggered.connect(self._on_navigate_next)

        # NAVIGATE
        self._navigate_menu = self.menuBar().addMenu("&Navigate")
        first_diff_action = self._navigate_menu.addAction("First Difference")
        first_diff_action.setShortcut(QKeySequence("Alt+Home"))
        first_diff_action.triggered.connect(self._on_navigate_first)

        prev_diff_action = self._navigate_menu.addAction("Previous Difference")
        prev_diff_action.setShortcut(QKeySequence("Alt+Up"))
        prev_diff_action.triggered.connect(self._on_navigate_prev)

        next_diff_action = self._navigate_menu.addAction("Next Difference")
        next_diff_action.setShortcut(QKeySequence("Alt+Down"))
        next_diff_action.triggered.connect(self._on_navigate_next)

        last_diff_action = self._navigate_menu.addAction("Last Difference")
        last_diff_action.setShortcut(QKeySequence("Alt+End"))
        last_diff_action.triggered.connect(self._on_navigate_last)

        # WINDOW
        self._window_menu = self.menuBar().addMenu("&Window")
        self._refresh_window_menu()

        # HELP
        help_menu = self.menuBar().addMenu("&Help")
        about_action = help_menu.addAction("About")
        about_action.triggered.connect(
            lambda: QMessageBox.information(self, "About", "WinMerge-compatible Python UI")
        )

    # Active-document helpers

    def _active_tab(self) -> _DocTab | None:
        idx = self._tab_widget.currentIndex()
        if 0 <= idx < len(self._docs):
            return self._docs[idx]
        return None

    @property
    def _active_doc(self) -> MergeDocument | DirDocument | None:
        tab = self._active_tab()
        return tab.doc if tab else None

    def _active_merge_doc(self) -> MergeDocument | None:
        doc = self._active_doc
        if isinstance(doc, MergeDocument):
            return doc
        return None

    # Tab management

    def _add_tab(self, tab: _DocTab) -> None:
        self._docs.append(tab)
        self._tab_widget.addTab(tab.view, tab.title)
        self._tab_widget.setCurrentIndex(len(self._docs) - 1)
        self._refresh_window_menu()

    def _find_tab_index(self, doc: MergeDocument | DirDocument) -> int:
        return next((i for i, t in enumerate(self._docs) if t.doc is doc), -1)

    def _update_tab_title(self, index: int, title: str) -> None:
        if 0 <= index < len(self._docs):
            self._docs[index].title = title
            self._tab_widget.setTabText(index, title)
            self._refresh_window_menu()

    def _close_tab(self, index: int) -> bool:
        """Close and clean up tab at index. Returns False if cancelled by user."""
        if not (0 <= index < len(self._docs)):
            return True
        tab = self._docs[index]
        if isinstance(tab.doc, MergeDocument) and tab.doc.is_modified():
            result = QMessageBox.question(
                self,
                "Unsaved changes",
                f"'{tab.title}' has unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if result == QMessageBox.StandardButton.Cancel:
                return False
            if result == QMessageBox.StandardButton.Save:
                tab.doc.save_all()
                if tab.doc.is_modified():
                    return False
        self._tab_widget.removeTab(index)
        self._docs.pop(index)
        self._refresh_window_menu()
        return True

    @Slot(int)
    def _on_tab_close_requested(self, index: int) -> None:
        self._close_tab(index)

    @Slot(int)
    def _on_tab_changed(self, _index: int) -> None:
        self._refresh_window_menu()

    @Slot()
    def _on_close_current_tab(self) -> None:
        self._close_tab(self._tab_widget.currentIndex())

    # Window menu

    def _refresh_window_menu(self) -> None:
        self._window_menu.clear()
        for i, tab in enumerate(self._docs):
            act = self._window_menu.addAction(f"{i + 1}. {tab.title}")
            act.setCheckable(True)
            act.setChecked(i == self._tab_widget.currentIndex())
            act.triggered.connect(lambda _checked, idx=i: self._tab_widget.setCurrentIndex(idx))

    # Navigate actions

    @Slot()
    def _on_navigate_first(self) -> None:
        doc = self._active_merge_doc()
        if doc and doc.get_block_count():
            doc.set_current_block(0)
            self.statusBar().showMessage("First difference.", 2000)

    @Slot()
    def _on_navigate_last(self) -> None:
        doc = self._active_merge_doc()
        if doc and doc.get_block_count():
            doc.set_current_block(doc.get_block_count() - 1)
            self.statusBar().showMessage("Last difference.", 2000)

    @Slot()
    def _on_navigate_prev(self) -> None:
        doc = self._active_merge_doc()
        if doc and doc.get_block_count():
            new_idx = doc.navigate_block(-1)
            self.statusBar().showMessage(f"Diff {new_idx + 1}/{doc.get_block_count()}.", 2000)

    @Slot()
    def _on_navigate_next(self) -> None:
        doc = self._active_merge_doc()
        if doc and doc.get_block_count():
            new_idx = doc.navigate_block(+1)
            self.statusBar().showMessage(f"Diff {new_idx + 1}/{doc.get_block_count()}.", 2000)

    # ?? Open dialog actions ???????????????????????????????????????????????????

    @Slot()
    def _on_open_dialog(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(self, "Open files for compare")
        if not selected:
            return
        request = OpenRequest(paths=[Path(p) for p in selected], mode=self._app_config.compare_mode)
        self.open_targets(request)

    @Slot()
    def _on_open_conflict_dialog(self) -> None:
        """Open a conflict file (e.g. Git <<< === >>> markers) as a 3-way merge."""
        selected, _ = QFileDialog.getOpenFileName(self, "Open Conflict File")
        if not selected:
            return
        self.open_targets(OpenRequest(paths=[Path(selected)], mode="conflict"))

    @Slot()
    def _on_open_clipboard(self) -> None:
        """Compare clipboard content against the active left pane (or as a new 2-way compare)."""
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            QMessageBox.information(self, "Clipboard", "Clipboard is empty or not text.")
            return
        self.open_targets(OpenRequest(paths=[], mode="clipboard", descriptions=["Clipboard", "Left Pane"]))

    # ?? Save actions ?????????????????????????????????????????????????????????

    @Slot()
    def _on_save_all_dirty(self) -> None:
        doc = self._active_merge_doc()
        if doc is None:
            QMessageBox.warning(self, "Save", "No active text compare document.")
            return
        saved_count = doc.save_all()
        self.statusBar().showMessage(f"Saved {saved_count} dirty pane(s).", 4000)

    @Slot()
    def _on_save_primary(self) -> None:
        doc = self._active_merge_doc()
        if doc is None:
            QMessageBox.warning(self, "Save", "No active text compare document.")
            return
        target_pane = MergeDocument.MIDDLE if doc.is_three_way_mode() else MergeDocument.LEFT
        self._on_save_pane(target_pane)

    @Slot()
    def _on_save_primary_as(self) -> None:
        doc = self._active_merge_doc()
        if doc is None:
            QMessageBox.warning(self, "Save As", "No active text compare document.")
            return
        target_pane = MergeDocument.MIDDLE if doc.is_three_way_mode() else MergeDocument.LEFT
        current_path = doc.get_pane_path(target_pane)
        start_dir = str(current_path.parent) if current_path is not None else ""
        selected, _ = QFileDialog.getSaveFileName(self, "Save pane as", start_dir)
        if not selected:
            return
        if doc.save_pane_as(target_pane, Path(selected)):
            self.statusBar().showMessage(f"Saved pane as {selected}", 4000)

    def _on_save_pane(self, pane: int) -> None:
        doc = self._active_merge_doc()
        if doc is None:
            QMessageBox.warning(self, "Save", "No active text compare document.")
            return
        if not doc.can_save_pane(pane):
            QMessageBox.warning(self, "Save", "Selected pane has no backing file path.")
            return
        if doc.save_pane(pane):
            pane_name = {MergeDocument.LEFT: "Left", MergeDocument.MIDDLE: "Middle", MergeDocument.RIGHT: "Right"}
            self.statusBar().showMessage(f"Saved {pane_name.get(pane, '?')} pane.", 4000)

    @Slot()
    def _on_rescan_from_disk(self) -> None:
        doc = self._active_merge_doc()
        if doc is None:
            QMessageBox.warning(self, "Rescan", "No active text compare document.")
            return
        if doc.rescan_from_disk():
            self.statusBar().showMessage("Rescanned from disk.", 4000)

    @Slot()
    def _on_undo(self) -> None:
        doc = self._active_merge_doc()
        if doc is None:
            return
        primary = MergeDocument.MIDDLE if doc.is_three_way_mode() else MergeDocument.LEFT
        for pane in (primary, MergeDocument.LEFT, MergeDocument.RIGHT):
            if doc.can_undo(pane):
                doc.undo(pane)
                self.statusBar().showMessage("Undo.", 2000)
                return

    @Slot()
    def _on_redo(self) -> None:
        doc = self._active_merge_doc()
        if doc is None:
            return
        primary = MergeDocument.MIDDLE if doc.is_three_way_mode() else MergeDocument.LEFT
        for pane in (primary, MergeDocument.LEFT, MergeDocument.RIGHT):
            if doc.can_redo(pane):
                doc.redo(pane)
                self.statusBar().showMessage("Redo.", 2000)
                return

    # ?? Core open routing (ShowMergeDoc / ShowHexMergeDoc equivalents) ????????

    def open_targets(self, request: OpenRequest) -> None:
        mode = request.mode

        # ?? conflict file: parse markers ??3-way temp files
        if mode == "conflict" and len(request.paths) == 1:
            self._open_conflict_doc(request.paths[0])
            return

        # ?? clipboard ??temp file
        if mode == "clipboard":
            self._open_clipboard_doc(request)
            return

        if len(request.paths) < 2:
            QMessageBox.warning(self, "Invalid input", "Select at least two paths.")
            return

        # ?? folder mode
        if mode == "folder" or all(path.is_dir() for path in request.paths):
            if len(request.paths) != 2:
                QMessageBox.warning(self, "Invalid input", "Folder compare supports exactly two folders.")
                return
            self._open_dir_doc(request)
            return

        # ?? text merge
        if len(request.paths) > 3:
            QMessageBox.warning(self, "Invalid input", "Text compare supports up to three files.")
            return
        self._open_merge_doc(request)

    def _open_merge_doc(self, request: OpenRequest) -> None:
        context = DiffContext(paths=request.paths, compare_mode="text")
        doc = MergeDocument(diff_context=context)
        # set descriptions from request if provided
        if request.descriptions:
            for i, desc in enumerate(request.descriptions):
                doc._descriptions[i] = desc
        doc.open_docs(request.paths)
        view = MergeViewWidget(document=doc)
        title = self._make_merge_title(request.paths)
        tab = _DocTab(doc, view, title)
        doc.saved.connect(lambda _pane, path: self.statusBar().showMessage(f"Saved {path}", 4000))
        doc.modified_changed.connect(lambda dirty, t=tab: self._on_doc_modified(t, dirty))
        self._add_tab(tab)

    def _open_dir_doc(self, request: OpenRequest) -> None:
        context = DiffContext(paths=request.paths, compare_mode="folder")
        doc = DirDocument(diff_context=context)
        view = DirViewWidget(document=doc)
        view.open_requested.connect(self._on_dir_view_open_requested)
        title = f"{request.paths[0].name} ??{request.paths[1].name}"
        tab = _DocTab(doc, view, title)
        self._add_tab(tab)
        doc.init_compare(request.paths)

    def _open_conflict_doc(self, conflict_path: Path) -> None:
        """Parse a conflict file with <<< === >>> markers into 3 temp panes."""
        try:
            raw = conflict_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            QMessageBox.critical(self, "Open Conflict", str(exc))
            return
        ours, base, theirs = _parse_conflict_markers(raw)
        td = tempfile.mkdtemp(prefix="winmerge_conflict_")
        left_f = Path(td) / "ours.txt"
        mid_f = Path(td) / "base.txt"
        right_f = Path(td) / "theirs.txt"
        left_f.write_text(ours, encoding="utf-8")
        mid_f.write_text(base, encoding="utf-8")
        right_f.write_text(theirs, encoding="utf-8")
        req = OpenRequest(
            paths=[left_f, mid_f, right_f],
            mode="text",
            descriptions=["Ours", "Base", "Theirs"],
        )
        self._open_merge_doc(req)

    def _open_clipboard_doc(self, request: OpenRequest) -> None:
        from PySide6.QtWidgets import QApplication
        clipboard_text = QApplication.clipboard().text()
        td = tempfile.mkdtemp(prefix="winmerge_clip_")
        clip_f = Path(td) / "clipboard.txt"
        clip_f.write_text(clipboard_text or "", encoding="utf-8")

        # Use active doc's left pane as the second file if available
        doc = self._active_merge_doc()
        if doc is not None:
            other_path = doc.get_pane_path(MergeDocument.LEFT)
        else:
            other_path = None

        if other_path is None:
            other_f = Path(td) / "empty.txt"
            other_f.write_text("", encoding="utf-8")
            other_path = other_f

        req = OpenRequest(
            paths=[clip_f, other_path],
            mode="text",
            descriptions=["Clipboard", other_path.name],
        )
        self._open_merge_doc(req)

    # ?? Helpers ???????????????????????????????????????????????????????????????

    @staticmethod
    def _make_merge_title(paths: list[Path]) -> str:
        if not paths:
            return "Compare"
        names = [p.name for p in paths if p.name]
        return " ??".join(names) if names else "Compare"

    def _on_doc_modified(self, tab: _DocTab, dirty: bool) -> None:
        idx = self._find_tab_index(tab.doc)
        if idx == -1:
            return
        title = tab.title.rstrip(" *")
        self._update_tab_title(idx, f"{title} *" if dirty else title)

    # ?? Close-event ???????????????????????????????????????????????????????????

    def closeEvent(self, event: QCloseEvent) -> None:
        for i in range(len(self._docs) - 1, -1, -1):
            if not self._close_tab(i):
                event.ignore()
                return
        event.accept()

    @Slot(object)
    def _on_dir_view_open_requested(self, paths: list[Path]) -> None:
        self.open_targets(OpenRequest(paths=paths, mode="text"))


# ??????????????????????????????????????????????????????????????????????????????
# Conflict marker parser
# ??????????????????????????????????????????????????????????????????????????????

def _parse_conflict_markers(text: str) -> tuple[str, str, str]:
    """Split a conflict file into (ours, base, theirs) sections.

    Supports both 2-way (<<< / >>>) and 3-way (<<< / ||| / === / >>>) formats.
    """
    ours_lines: list[str] = []
    base_lines: list[str] = []
    theirs_lines: list[str] = []
    section = "normal"   # normal | ours | base | theirs

    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n")
        if stripped.startswith("<<<<<<<"):
            section = "ours"
        elif stripped.startswith("|||||||"):
            section = "base"
        elif stripped.startswith("======="):
            section = "theirs"
        elif stripped.startswith(">>>>>>>"):
            section = "normal"
        else:
            if section == "normal":
                ours_lines.append(line)
                base_lines.append(line)
                theirs_lines.append(line)
            elif section == "ours":
                ours_lines.append(line)
            elif section == "base":
                base_lines.append(line)
            elif section == "theirs":
                theirs_lines.append(line)

    return "".join(ours_lines), "".join(base_lines), "".join(theirs_lines)
