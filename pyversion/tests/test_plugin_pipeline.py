from pathlib import Path

from core.diff_context import DiffContext
from core.diff_wrapper import DiffWrapper


def test_prediff_plugin_hook(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"

    left.write_text("ID=123\n", encoding="utf-8")
    right.write_text("ID=999\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")

    def strip_digits(text: str, _path: Path) -> str:
        return "".join(ch for ch in text if not ch.isdigit())

    context.plugin_manager.register("prediff", strip_digits)

    wrapper = DiffWrapper(context)
    count = wrapper.run_file_diff(left, right)

    assert count == 0
