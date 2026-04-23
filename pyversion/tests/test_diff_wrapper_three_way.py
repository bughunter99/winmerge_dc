from pathlib import Path

from core.diff_context import DiffContext
from core.diff_wrapper import DiffWrapper


def test_diff_wrapper_three_way(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    middle = tmp_path / "middle.txt"
    right = tmp_path / "right.txt"

    left.write_text("A\nB\nC\n", encoding="utf-8")
    middle.write_text("A\nBB\nC\n", encoding="utf-8")
    right.write_text("A\nBB\nCC\n", encoding="utf-8")

    context = DiffContext(paths=[left, middle, right], compare_mode="text")
    wrapper = DiffWrapper(context)

    summary = wrapper.run_three_way_diff(left, middle, right)

    assert summary.left_middle_diffs >= 1
    assert summary.middle_right_diffs >= 1
    assert summary.total_diffs == summary.left_middle_diffs + summary.middle_right_diffs
