"""Tests for DirDocument/DiffThreadController pause, resume, and rescan APIs."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from core.diff_context import DiffContext
from docs.dir_doc import DirDocument


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_dir_doc_pause_resume_flags(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = DirDocument(context)

    assert doc.is_compare_paused() is False
    doc.pause_compare()
    assert doc.is_compare_paused() is True
    doc.continue_compare()
    assert doc.is_compare_paused() is False


def test_dir_doc_rescan_resets_roots(tmp_path: Path, qapp) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = DirDocument(context)
    # Set roots directly without spawning compare thread
    doc.left_root = left
    doc.right_root = right

    # Verify rescan with new paths updates roots
    new_left = tmp_path / "new_left"
    new_right = tmp_path / "new_right"
    new_left.mkdir()
    new_right.mkdir()

    doc.rescan(paths=[new_left, new_right])
    doc.abort_compare()  # clean up thread immediately

    assert doc.left_root == new_left
    assert doc.right_root == new_right


@pytest.mark.skip(reason="Qt thread teardown crashes pytest runner on Windows")
def test_dir_doc_refresh_selected_starts_compare(tmp_path: Path, qapp) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "a.txt").write_text("hello", encoding="utf-8")
    (right / "a.txt").write_text("hello", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = DirDocument(context)

    from core.models import FilePairResult

    items = [
        FilePairResult(
            left=left / "a.txt",
            right=right / "a.txt",
            diff_count=0,
            status="identical",
        )
    ]
    # Should not raise; starts a new sub-compare thread
    doc.refresh_selected(items)
    doc.abort_compare()

