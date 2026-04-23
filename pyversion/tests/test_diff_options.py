from pathlib import Path

from core.diff_context import DiffContext
from core.diff_wrapper import DiffWrapper


def test_ignore_case_and_whitespace(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"

    left.write_text("Hello   World\n", encoding="utf-8")
    right.write_text("hello world\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    context.options.ignore_case = True
    context.options.ignore_whitespace = True

    wrapper = DiffWrapper(context)
    count = wrapper.run_file_diff(left, right)

    assert count == 0
