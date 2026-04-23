from pathlib import Path

from core.folder_scan import collect_file_pairs


def test_collect_file_pairs_basic(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()

    (left / "same.txt").write_text("a", encoding="utf-8")
    (right / "same.txt").write_text("b", encoding="utf-8")
    (left / "left_only.txt").write_text("x", encoding="utf-8")
    (right / "right_only.txt").write_text("y", encoding="utf-8")

    result = collect_file_pairs(left, right, recursive=True)

    assert len(result.matched_pairs) == 1
    assert len(result.left_only) == 1
    assert len(result.right_only) == 1
