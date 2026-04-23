from __future__ import annotations

from pathlib import Path

from core.diff_context import DiffContext
from docs.dir_doc import DirDocument
from ui.dir_views import DirViewWidget


def test_populates_side_only_items(tmp_path: Path, qapp) -> None:
    left_root = tmp_path / "left"
    right_root = tmp_path / "right"
    left_root.mkdir()
    right_root.mkdir()

    context = DiffContext(paths=[left_root, right_root], compare_mode="folder")
    document = DirDocument(context)
    view = DirViewWidget(document)

    left_only = left_root / "left_only.txt"
    right_only = right_root / "right_only.txt"
    document.scan_result.left_only = [left_only]
    document.scan_result.right_only = [right_only]

    view._populate_side_only_items()

    assert view._tree.topLevelItemCount() == 2
    statuses = {view._tree.topLevelItem(i).text(4) for i in range(view._tree.topLevelItemCount())}
    assert statuses == {"left-only", "right-only"}


def test_double_click_emits_open_requested(tmp_path: Path, qapp) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("a\n", encoding="utf-8")
    right.write_text("b\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="folder")
    document = DirDocument(context)
    view = DirViewWidget(document)

    received: list[list[Path]] = []
    view.open_requested.connect(received.append)

    result = type("Result", (), {"left": left, "right": right, "diff_count": 1, "status": "different"})()
    view._on_item_ready(result)
    item = view._tree.topLevelItem(0)

    view._on_item_double_clicked(item, 0)

    assert received == [[left, right]]
