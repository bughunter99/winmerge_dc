"""Tests for block navigation (prev/next) in MergeDocument."""
from __future__ import annotations

import pytest

from core.diff_context import DiffContext, DiffOptions
from docs.merge_doc import MergeDocument


def _make_doc() -> MergeDocument:
    ctx = DiffContext(paths=[], compare_mode="text", options=DiffOptions())
    return MergeDocument(ctx)


def _open_three_way(doc: MergeDocument, left: list[str], middle: list[str], right: list[str]) -> None:
    """Inject pane lines directly and rebuild blocks without file I/O."""
    doc._pane_lines = {
        MergeDocument.LEFT: list(left),
        MergeDocument.MIDDLE: list(middle),
        MergeDocument.RIGHT: list(right),
    }
    doc.opened_paths = [None, None, None]  # mark as 3-way
    doc._emit_three_way_summary_and_blocks(update_stats=False)


def test_navigate_next_clamps_at_end():
    doc = _make_doc()
    left =   ["a", "B", "c", "D", "e"]
    middle = ["a", "b", "c", "d", "e"]
    right =  ["a", "b", "c", "X", "e"]
    _open_three_way(doc, left, middle, right)

    total = doc.get_block_count()
    assert total >= 1

    # Navigate past the end — must not exceed total-1
    for _ in range(total + 5):
        doc.navigate_block(1)
    assert doc.current_block == total - 1


def test_navigate_prev_clamps_at_start():
    doc = _make_doc()
    left =   ["a", "B", "c"]
    middle = ["a", "b", "c"]
    right =  ["a", "b", "c"]
    _open_three_way(doc, left, middle, right)

    doc.navigate_block(1)  # move to 1 if exists, else stays 0
    for _ in range(10):
        doc.navigate_block(-1)
    assert doc.current_block == 0


def test_navigate_emits_signal():
    doc = _make_doc()
    left =   ["A", "b", "c", "D"]
    middle = ["a", "b", "c", "d"]
    right =  ["a", "b", "c", "d"]
    _open_three_way(doc, left, middle, right)

    received: list[int] = []
    doc.current_block_changed.connect(received.append)

    doc.navigate_block(1)
    assert len(received) == 1
    assert received[0] == doc.current_block


def test_set_current_block():
    doc = _make_doc()
    left =   ["A", "b", "C", "d"]
    middle = ["a", "b", "c", "d"]
    right =  ["a", "b", "X", "d"]
    _open_three_way(doc, left, middle, right)

    total = doc.get_block_count()
    if total >= 2:
        doc.set_current_block(1)
        assert doc.current_block == 1

    # Out-of-range clamps
    doc.set_current_block(9999)
    assert doc.current_block == total - 1


def test_blocks_snapshot_length_matches():
    doc = _make_doc()
    left =   ["A", "b", "c"]
    middle = ["a", "b", "c"]
    right =  ["a", "b", "c"]
    _open_three_way(doc, left, middle, right)

    assert len(doc.get_blocks_snapshot()) == doc.get_block_count()
