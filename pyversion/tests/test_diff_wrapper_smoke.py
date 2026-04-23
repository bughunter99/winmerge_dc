from pathlib import Path

from core.diff_context import DiffContext
from core.diff_wrapper import DiffWrapper


def test_diff_wrapper_smoke(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("a\nb\nc\n", encoding="utf-8")
    right.write_text("a\nbb\nc\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    wrapper = DiffWrapper(context)

    count = wrapper.run_file_diff(left, right)

    assert count >= 1
    assert context.diff_list.count() >= 1
