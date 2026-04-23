from pathlib import Path

from core.diff_context import DiffContext
from docs.merge_doc import MergeDocument


def test_merge_blocks_and_conflicts(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    middle = tmp_path / "middle.txt"
    right = tmp_path / "right.txt"

    left.write_text("A\nL\nC\n", encoding="utf-8")
    middle.write_text("A\nM\nC\n", encoding="utf-8")
    right.write_text("A\nR\nC\n", encoding="utf-8")

    context = DiffContext(paths=[left, middle, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, middle, right])

    assert doc.is_three_way_mode()
    assert doc.get_block_count() >= 1
    assert doc.get_conflict_count() >= 1


def test_apply_merge_block(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    middle = tmp_path / "middle.txt"
    right = tmp_path / "right.txt"

    left.write_text("A\nB\nC\n", encoding="utf-8")
    middle.write_text("A\nX\nC\n", encoding="utf-8")
    right.write_text("A\nX\nC\n", encoding="utf-8")

    context = DiffContext(paths=[left, middle, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, middle, right])

    first_block = doc.get_block(0)
    src_start, src_end = first_block.ranges[MergeDocument.LEFT]

    ok = doc.apply_merge_block(MergeDocument.LEFT, MergeDocument.MIDDLE, 0)

    assert ok is True
    assert doc.is_dirty(MergeDocument.MIDDLE)
    expected = doc.get_pane_text(MergeDocument.LEFT).split("\n")
    got = doc.get_pane_text(MergeDocument.MIDDLE).split("\n")
    assert expected[src_start:src_end] == got[src_start:src_end]
