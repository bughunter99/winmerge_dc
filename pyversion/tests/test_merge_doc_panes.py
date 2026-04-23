from pathlib import Path

from core.diff_context import DiffContext
from docs.merge_doc import MergeDocument


def test_two_way_pane_snapshot(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("L1\nL2\n", encoding="utf-8")
    right.write_text("R1\nR2\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)

    snapshots: list[tuple[str, str, str]] = []
    doc.pane_texts_changed.connect(lambda l, m, r: snapshots.append((l, m, r)))

    doc.open_docs([left, right])

    assert snapshots
    left_text, middle_text, right_text = snapshots[-1]
    assert "L1" in left_text
    assert middle_text == ""
    assert "R1" in right_text
