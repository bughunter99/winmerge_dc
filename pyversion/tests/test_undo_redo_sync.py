"""Tests for undo/redo and sync-point features of MergeDocument."""
from __future__ import annotations

from pathlib import Path

from core.diff_context import DiffContext
from docs.merge_doc import MergeDocument


# ---------------------------------------------------------------------------
# Undo/redo
# ---------------------------------------------------------------------------


def _make_doc(tmp_path: Path, left_text: str = "A\nB\n", right_text: str = "X\nY\n") -> MergeDocument:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text(left_text, encoding="utf-8")
    right.write_text(right_text, encoding="utf-8")
    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])
    return doc


def test_undo_restores_previous_pane_text(tmp_path: Path) -> None:
    doc = _make_doc(tmp_path)
    original_left = doc.get_pane_text(MergeDocument.LEFT)

    doc.update_pane_text(MergeDocument.LEFT, "CHANGED\nTEXT\n")
    assert doc.get_pane_text(MergeDocument.LEFT) != original_left
    assert doc.can_undo(MergeDocument.LEFT) is True

    ok = doc.undo(MergeDocument.LEFT)

    assert ok is True
    assert doc.get_pane_text(MergeDocument.LEFT) == original_left


def test_redo_re_applies_after_undo(tmp_path: Path) -> None:
    doc = _make_doc(tmp_path)
    doc.update_pane_text(MergeDocument.LEFT, "CHANGED\n")
    changed = doc.get_pane_text(MergeDocument.LEFT)

    doc.undo(MergeDocument.LEFT)
    assert doc.can_redo(MergeDocument.LEFT) is True

    ok = doc.redo(MergeDocument.LEFT)

    assert ok is True
    assert doc.get_pane_text(MergeDocument.LEFT) == changed


def test_undo_clears_redo_stack_on_new_edit(tmp_path: Path) -> None:
    doc = _make_doc(tmp_path)
    doc.update_pane_text(MergeDocument.LEFT, "FIRST\n")
    doc.undo(MergeDocument.LEFT)
    assert doc.can_redo(MergeDocument.LEFT) is True

    # New edit should clear redo
    doc.update_pane_text(MergeDocument.LEFT, "SECOND\n")
    assert doc.can_redo(MergeDocument.LEFT) is False


def test_undo_noop_when_stack_empty(tmp_path: Path) -> None:
    doc = _make_doc(tmp_path)
    assert doc.can_undo(MergeDocument.LEFT) is False
    ok = doc.undo(MergeDocument.LEFT)
    assert ok is False


def test_undo_after_open_clears_history(tmp_path: Path) -> None:
    """open_docs should reset undo/redo stacks."""
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("A\n", encoding="utf-8")
    right.write_text("B\n", encoding="utf-8")
    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])
    doc.update_pane_text(MergeDocument.LEFT, "DIRTY\n")
    assert doc.can_undo(MergeDocument.LEFT) is True

    # Re-open
    doc.open_docs([left, right])
    assert doc.can_undo(MergeDocument.LEFT) is False
    assert doc.can_redo(MergeDocument.LEFT) is False


def test_modified_signal_emitted_false_after_full_undo(tmp_path: Path) -> None:
    doc = _make_doc(tmp_path)
    states: list[bool] = []
    doc.modified_changed.connect(states.append)

    doc.update_pane_text(MergeDocument.LEFT, "DIRTY\n")
    doc.undo(MergeDocument.LEFT)

    # After undo back to clean state, modified_changed(False) should be emitted
    assert states[-1] is False


def test_clear_undo_redo_removes_history(tmp_path: Path) -> None:
    doc = _make_doc(tmp_path)
    doc.update_pane_text(MergeDocument.LEFT, "DIRTY\n")
    assert doc.can_undo(MergeDocument.LEFT) is True

    doc.clear_undo_redo(MergeDocument.LEFT)

    assert doc.can_undo(MergeDocument.LEFT) is False
    assert doc.can_redo(MergeDocument.LEFT) is False


# ---------------------------------------------------------------------------
# Sync points
# ---------------------------------------------------------------------------


def test_sync_point_add_and_retrieve(tmp_path: Path) -> None:
    doc = _make_doc(tmp_path)
    doc.add_sync_point(5)
    doc.add_sync_point(2)
    doc.add_sync_point(9)

    pts = doc.get_sync_points()

    assert pts == [2, 5, 9]  # sorted


def test_sync_point_deduplicated(tmp_path: Path) -> None:
    doc = _make_doc(tmp_path)
    doc.add_sync_point(3)
    doc.add_sync_point(3)

    assert doc.get_sync_points() == [3]


def test_sync_point_remove(tmp_path: Path) -> None:
    doc = _make_doc(tmp_path)
    doc.add_sync_point(4)
    removed = doc.remove_sync_point(4)
    not_removed = doc.remove_sync_point(99)

    assert removed is True
    assert not_removed is False
    assert doc.get_sync_points() == []


def test_sync_point_navigate_by_index(tmp_path: Path) -> None:
    doc = _make_doc(tmp_path)
    doc.add_sync_point(10)
    doc.add_sync_point(20)

    assert doc.navigate_to_sync_point(0) == 10
    assert doc.navigate_to_sync_point(1) == 20
    assert doc.navigate_to_sync_point(99) is None


def test_sync_points_cleared(tmp_path: Path) -> None:
    doc = _make_doc(tmp_path)
    doc.add_sync_point(1)
    doc.add_sync_point(2)
    doc.clear_sync_points()

    assert doc.get_sync_points() == []
