from pathlib import Path

from core.diff_context import DiffContext
from core.diff_wrapper import DiffWrapper


def test_diff_wrapper_accumulate_mode(tmp_path: Path) -> None:
    l1 = tmp_path / "l1.txt"
    r1 = tmp_path / "r1.txt"
    l2 = tmp_path / "l2.txt"
    r2 = tmp_path / "r2.txt"

    l1.write_text("a\n", encoding="utf-8")
    r1.write_text("b\n", encoding="utf-8")
    l2.write_text("x\n", encoding="utf-8")
    r2.write_text("y\n", encoding="utf-8")

    context = DiffContext(paths=[l1, r1], compare_mode="folder")
    wrapper = DiffWrapper(context)

    wrapper.run_file_diff(l1, r1, reset_diff_list=True)
    first_count = context.diff_list.count()
    wrapper.run_file_diff(l2, r2, reset_diff_list=False)

    assert first_count >= 1
    assert context.diff_list.count() >= 2
