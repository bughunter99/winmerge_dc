from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

_COLOR_CONFLICT = QColor(255, 160, 160)  # red-ish
_COLOR_CHANGE = QColor(255, 255, 160)    # yellow-ish
_COLOR_CURRENT = QColor(160, 200, 255)   # blue-ish (current block overlay)

from docs.merge_doc import MergeDocument


class MergeViewWidget(QWidget):
    def __init__(self, document: MergeDocument) -> None:
        super().__init__()
        self._doc = document
        self._status = QLabel("Ready")
        self._mode = QLabel("2-way")
        self._last_action = QLabel("Merge: none")
        self._block_status = QLabel("Diff blocks: 0")
        self._pane_info = QLabel("Panes: -")

        self._header_panel = QWidget()
        self._header_layout = QHBoxLayout(self._header_panel)
        self._left_header = QLabel("1st File")
        self._middle_header = QLabel("2nd File")
        self._right_header = QLabel("3rd File")
        for hdr in (self._left_header, self._middle_header, self._right_header):
            hdr.setFrameStyle(QFrame.Shape.Panel | QFrame.Shadow.Sunken)
            hdr.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._header_layout.addWidget(hdr)

        self._pane_splitter = QSplitter(Qt.Horizontal)
        self._left_edit = QPlainTextEdit()
        self._middle_edit = QPlainTextEdit()
        self._right_edit = QPlainTextEdit()
        self._syncing_scroll = False
        self._button_panel = QWidget()
        self._button_layout = QGridLayout(self._button_panel)
        self._block_panel = QWidget()
        self._block_layout = QHBoxLayout(self._block_panel)
        self._block_index = QSpinBox()
        self._block_index.setMinimum(0)
        self._block_index.setMaximum(0)
        self._block_copy_lm = QPushButton("Copy Block L->M")
        self._block_copy_mr = QPushButton("Copy Block M->R")
        self._prev_block_btn = QPushButton("Prev")
        self._next_block_btn = QPushButton("Next")
        self._pane_edits: list[QPlainTextEdit] = [
            self._left_edit, self._middle_edit, self._right_edit
        ]
        self._edit_toggle_btn = QPushButton("Edit")
        self._recompare_btn = QPushButton("Recompare")
        self._recompare_btn.setEnabled(False)
        self._editing = False

        layout = QVBoxLayout(self)
        top_bar = QWidget()
        top_bar_layout = QHBoxLayout(top_bar)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.addWidget(QLabel("Mode:"))
        top_bar_layout.addWidget(self._mode)
        top_bar_layout.addSpacing(16)
        top_bar_layout.addWidget(self._status)
        top_bar_layout.addSpacing(16)
        top_bar_layout.addWidget(self._block_status)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self._last_action)

        layout.addWidget(top_bar)
        layout.addWidget(self._pane_info)
        layout.addWidget(self._header_panel)
        layout.addWidget(self._pane_splitter)
        layout.addWidget(self._button_panel)
        layout.addWidget(self._block_panel)

        _edit_bar = QWidget()
        _edit_hbox = QHBoxLayout(_edit_bar)
        _edit_hbox.addWidget(self._edit_toggle_btn)
        _edit_hbox.addWidget(self._recompare_btn)
        _edit_hbox.addStretch()
        layout.addWidget(_edit_bar)

        self._pane_splitter.addWidget(self._left_edit)
        self._pane_splitter.addWidget(self._middle_edit)
        self._pane_splitter.addWidget(self._right_edit)
        self._pane_splitter.setStretchFactor(0, 1)
        self._pane_splitter.setStretchFactor(1, 1)
        self._pane_splitter.setStretchFactor(2, 1)
        self._left_edit.setReadOnly(True)
        self._middle_edit.setReadOnly(True)
        self._right_edit.setReadOnly(True)
        self._wire_scroll_sync()

        self._block_layout.addWidget(QLabel("Block Index:"))
        self._block_layout.addWidget(self._block_index)
        self._block_layout.addWidget(self._block_copy_lm)
        self._block_layout.addWidget(self._block_copy_mr)
        self._block_layout.addWidget(self._prev_block_btn)
        self._block_layout.addWidget(self._next_block_btn)

        self._add_merge_button("L -> M", MergeDocument.LEFT, MergeDocument.MIDDLE, 0, 0)
        self._add_merge_button("L -> R", MergeDocument.LEFT, MergeDocument.RIGHT, 0, 1)
        self._add_merge_button("M -> L", MergeDocument.MIDDLE, MergeDocument.LEFT, 1, 0)
        self._add_merge_button("M -> R", MergeDocument.MIDDLE, MergeDocument.RIGHT, 1, 1)
        self._add_merge_button("R -> L", MergeDocument.RIGHT, MergeDocument.LEFT, 2, 0)
        self._add_merge_button("R -> M", MergeDocument.RIGHT, MergeDocument.MIDDLE, 2, 1)
        self._set_merge_buttons_enabled(False)
        self._set_block_buttons_enabled(False)

        self._block_copy_lm.clicked.connect(self._on_block_lm)
        self._block_copy_mr.clicked.connect(self._on_block_mr)
        self._prev_block_btn.clicked.connect(lambda: self._doc.navigate_block(-1))
        self._next_block_btn.clicked.connect(lambda: self._doc.navigate_block(1))
        self._edit_toggle_btn.clicked.connect(self._on_toggle_edit)
        self._recompare_btn.clicked.connect(self._on_recompare)

        self._doc.diff_ready.connect(self._on_diff_ready)
        self._doc.three_way_diff_ready.connect(self._on_three_way_diff_ready)
        self._doc.pane_texts_changed.connect(self._on_pane_texts_changed)
        self._doc.blocks_updated.connect(self._on_blocks_updated)
        self._doc.current_block_changed.connect(self._on_current_block_changed)
        self._doc.merge_applied.connect(self._on_merge_applied)
        self._doc.block_merge_applied.connect(self._on_block_merge_applied)
        self._doc.modified_changed.connect(self._on_modified_changed)
        self._doc.pane_metadata_changed.connect(self._on_pane_metadata_changed)
        self._doc.saved.connect(self._on_saved)
        self._doc.failed.connect(self._on_failed)

    def _add_merge_button(self, label: str, src: int, dst: int, row: int, col: int) -> None:
        button = QPushButton(label)
        button.clicked.connect(lambda _checked=False, s=src, d=dst: self._doc.apply_merge_copy(s, d))
        self._button_layout.addWidget(button, row, col)

    def _set_merge_buttons_enabled(self, enabled: bool) -> None:
        for index in range(self._button_layout.count()):
            item = self._button_layout.itemAt(index)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.setEnabled(enabled)

    def _set_block_buttons_enabled(self, enabled: bool) -> None:
        self._block_copy_lm.setEnabled(enabled)
        self._block_copy_mr.setEnabled(enabled)
        self._block_index.setEnabled(enabled)

    def _wire_scroll_sync(self) -> None:
        self._left_edit.verticalScrollBar().valueChanged.connect(
            lambda value: self._sync_vertical_scroll(self._left_edit, value)
        )
        self._middle_edit.verticalScrollBar().valueChanged.connect(
            lambda value: self._sync_vertical_scroll(self._middle_edit, value)
        )
        self._right_edit.verticalScrollBar().valueChanged.connect(
            lambda value: self._sync_vertical_scroll(self._right_edit, value)
        )

    def _sync_vertical_scroll(self, source: QPlainTextEdit, value: int) -> None:
        if self._syncing_scroll:
            return
        self._syncing_scroll = True
        for editor in (self._left_edit, self._middle_edit, self._right_edit):
            if editor is source:
                continue
            editor.verticalScrollBar().setValue(value)
        self._syncing_scroll = False

    def _on_diff_ready(self, diff_count: int) -> None:
        self._mode.setText("2-way")
        self._status.setText(f"Differences: {diff_count}")
        self._set_merge_buttons_enabled(False)
        self._set_block_buttons_enabled(False)
        self._block_status.setText("Diff blocks: 0")
        self._refresh_headers()

    def _on_three_way_diff_ready(self, left_middle: int, middle_right: int, total: int) -> None:
        self._mode.setText("3-way")
        self._status.setText(
            "Differences: "
            f"L-M={left_middle}, M-R={middle_right}, Total={total}"
        )
        self._set_merge_buttons_enabled(True)
        self._set_block_buttons_enabled(True)
        self._refresh_headers()

    def _on_pane_texts_changed(self, left_text: str, middle_text: str, right_text: str) -> None:
        # When in edit mode, only update panes that the user has NOT modified
        texts = [left_text, middle_text, right_text]
        pane_edits = [self._left_edit, self._middle_edit, self._right_edit]
        panes = [MergeDocument.LEFT, MergeDocument.MIDDLE, MergeDocument.RIGHT]
        for pane, editor, text in zip(panes, pane_edits, texts):
            if self._editing and self._doc.is_dirty(pane):
                continue  # keep user's edits
            editor.setPlainText(text)
        self._apply_highlights()
        self._refresh_pane_info()

    def _apply_highlights(self, scroll_to_current: bool = False) -> None:
        """Color-code diff blocks across all 3 panes using ExtraSelections."""
        blocks = self._doc.get_blocks_snapshot()
        current = self._doc.current_block
        pane_map = {
            MergeDocument.LEFT: self._left_edit,
            MergeDocument.MIDDLE: self._middle_edit,
            MergeDocument.RIGHT: self._right_edit,
        }
        # Clear all extra selections first
        for editor in pane_map.values():
            editor.setExtraSelections([])

        if not blocks:
            return

        selections: dict[int, list] = {k: [] for k in pane_map}

        for block in blocks:
            is_current = (block.index == current)
            base_color = _COLOR_CONFLICT if block.is_conflict else _COLOR_CHANGE
            fg = QTextCharFormat()
            fg.setBackground(base_color)
            cur_fmt = QTextCharFormat()
            cur_fmt.setBackground(_COLOR_CURRENT)

            for pane, editor in pane_map.items():
                start_line, end_line = block.ranges.get(pane, (0, 0))
                if start_line == end_line:
                    continue
                doc = editor.document()
                start_block = doc.findBlockByLineNumber(start_line)
                end_block = doc.findBlockByLineNumber(max(end_line - 1, start_line))
                if not start_block.isValid() or not end_block.isValid():
                    continue

                sel = QPlainTextEdit.ExtraSelection()
                cursor = QTextCursor(start_block)
                cursor.movePosition(QTextCursor.EndOfBlock, QTextCursor.KeepAnchor)
                end_cursor = QTextCursor(end_block)
                end_cursor.movePosition(QTextCursor.EndOfBlock)
                cursor.setPosition(start_block.position())
                cursor.setPosition(end_block.position() + end_block.length() - 1, QTextCursor.KeepAnchor)
                sel.cursor = cursor
                sel.format = cur_fmt if is_current else fg
                selections[pane].append(sel)

        for pane, editor in pane_map.items():
            editor.setExtraSelections(selections[pane])

        if scroll_to_current and blocks:
            # Scroll every pane to show the current block
            block = self._doc.get_block(current)
            for pane, editor in pane_map.items():
                start_line, _ = block.ranges.get(pane, (0, 0))
                doc = editor.document()
                tb = doc.findBlockByLineNumber(start_line)
                if tb.isValid():
                    cursor = QTextCursor(tb)
                    editor.setTextCursor(cursor)
                    editor.ensureCursorVisible()

    def _on_blocks_updated(self, total_blocks: int, conflict_blocks: int) -> None:
        self._block_status.setText(f"Diff blocks: {total_blocks} (conflicts: {conflict_blocks})")
        self._block_index.setMaximum(max(total_blocks - 1, 0))
        self._apply_highlights()

    def _on_current_block_changed(self, index: int) -> None:
        self._block_index.setValue(index)
        self._apply_highlights(scroll_to_current=True)

    def _on_merge_applied(self, src: int, dst: int, remaining_total: int) -> None:
        pane_name = {MergeDocument.LEFT: "L", MergeDocument.MIDDLE: "M", MergeDocument.RIGHT: "R"}
        self._last_action.setText(f"Merge: {pane_name.get(src, '?')} -> {pane_name.get(dst, '?')} (remain={remaining_total})")

    def _on_block_merge_applied(self, block_index: int, src: int, dst: int, remaining_total: int) -> None:
        pane_name = {MergeDocument.LEFT: "L", MergeDocument.MIDDLE: "M", MergeDocument.RIGHT: "R"}
        self._last_action.setText(f"Merge: block#{block_index} {pane_name.get(src, '?')} -> {pane_name.get(dst, '?')} (remain={remaining_total})")

    def _on_block_lm(self) -> None:
        self._doc.apply_merge_block(MergeDocument.LEFT, MergeDocument.MIDDLE, self._block_index.value())

    def _on_block_mr(self) -> None:
        self._doc.apply_merge_block(MergeDocument.MIDDLE, MergeDocument.RIGHT, self._block_index.value())

    def _on_saved(self, pane: int, path: str) -> None:
        pane_name = {MergeDocument.LEFT: "L", MergeDocument.MIDDLE: "M", MergeDocument.RIGHT: "R"}
        self._status.setText(f"Saved {pane_name.get(pane, '?')} pane to {path}")
        self._refresh_pane_info()
        self._refresh_headers()

    def _on_modified_changed(self, _modified: bool) -> None:
        self._refresh_pane_info()

    def _on_pane_metadata_changed(self, _pane: int) -> None:
        self._refresh_pane_info()
        self._refresh_headers()

    def _on_failed(self, message: str) -> None:
        self._status.setText(f"Error: {message}")

    def _on_toggle_edit(self) -> None:
        self._editing = not self._editing
        if self._editing:
            self._edit_toggle_btn.setText("Lock")
            self._recompare_btn.setEnabled(True)
            for pane, editor in zip((MergeDocument.LEFT, MergeDocument.MIDDLE, MergeDocument.RIGHT), self._pane_edits):
                editor.setReadOnly(self._doc.get_read_only(pane))
        else:
            self._edit_toggle_btn.setText("Edit")
            self._recompare_btn.setEnabled(False)
            for editor in self._pane_edits:
                editor.setReadOnly(True)

    def _on_recompare(self) -> None:
        # Push current editor contents into the document, then recompare
        pane_edits = [
            (MergeDocument.LEFT, self._left_edit),
            (MergeDocument.MIDDLE, self._middle_edit),
            (MergeDocument.RIGHT, self._right_edit),
        ]
        for pane, editor in pane_edits:
            self._doc.update_pane_text(pane, editor.toPlainText())
        self._doc.recompare()

    def _refresh_pane_info(self) -> None:
        parts: list[str] = []
        pane_names = {MergeDocument.LEFT: "L", MergeDocument.MIDDLE: "M", MergeDocument.RIGHT: "R"}
        for pane in (MergeDocument.LEFT, MergeDocument.MIDDLE, MergeDocument.RIGHT):
            desc = self._doc.get_description(pane) or "-"
            fmt = self._doc.get_pane_format(pane)
            fmt_text = "-/-"
            if fmt is not None:
                eol_name = {"\n": "LF", "\r\n": "CRLF", "\r": "CR"}.get(fmt.newline, repr(fmt.newline))
                mixed = ",mixed" if fmt.mixed_eol else ""
                fmt_text = f"{fmt.encoding}/{eol_name}{mixed}"
            dirty = "*" if self._doc.is_dirty(pane) else ""
            ro = ",RO" if self._doc.get_read_only(pane) else ""
            parts.append(f"{pane_names[pane]}:{desc} [{fmt_text}{ro}]{dirty}")
        self._pane_info.setText(" | ".join(parts))

    def _refresh_headers(self) -> None:
        names = {
            MergeDocument.LEFT: "1st File",
            MergeDocument.MIDDLE: "2nd File",
            MergeDocument.RIGHT: "3rd File",
        }
        labels = {
            MergeDocument.LEFT: self._left_header,
            MergeDocument.MIDDLE: self._middle_header,
            MergeDocument.RIGHT: self._right_header,
        }
        for pane in (MergeDocument.LEFT, MergeDocument.MIDDLE, MergeDocument.RIGHT):
            desc = self._doc.get_description(pane) or names[pane]
            labels[pane].setText(desc)