from pathlib import Path

from core.diff_context import DiffContext
from docs.merge_doc import MergeDocument


def test_merge_copy_reduces_three_way_diff(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    middle = tmp_path / "middle.txt"
    right = tmp_path / "right.txt"

    left.write_text("A\nB\n", encoding="utf-8")
    middle.write_text("A\nX\n", encoding="utf-8")
    right.write_text("A\nY\n", encoding="utf-8")

    context = DiffContext(paths=[left, middle, right], compare_mode="text")
    doc = MergeDocument(context)

    captured_totals: list[int] = []
    doc.three_way_diff_ready.connect(lambda _lm, _mr, total: captured_totals.append(total))

    doc.open_docs([left, middle, right])
    assert doc.is_three_way_mode()
    assert captured_totals[-1] >= 1

    ok = doc.apply_merge_copy(MergeDocument.LEFT, MergeDocument.MIDDLE)
    assert ok is True
    assert doc.is_dirty(MergeDocument.MIDDLE)
    assert doc.get_pane_text(MergeDocument.MIDDLE) == doc.get_pane_text(MergeDocument.LEFT)

    # After L->M, left-middle part should be resolved, so total should not increase.
    assert captured_totals[-1] <= captured_totals[0]


def test_merge_copy_requires_three_way_mode(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("A\n", encoding="utf-8")
    right.write_text("B\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])

    ok = doc.apply_merge_copy(MergeDocument.LEFT, MergeDocument.RIGHT)
    assert ok is False


def test_save_pane_writes_edited_text_and_clears_dirty(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("A\n", encoding="utf-8")
    right.write_text("B\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])

    doc.update_pane_text(MergeDocument.LEFT, "A\nEdited")

    ok = doc.save_pane(MergeDocument.LEFT)

    assert ok is True
    assert doc.is_dirty(MergeDocument.LEFT) is False
    assert left.read_text(encoding="utf-8") == "A\nEdited\n"


def test_save_all_saves_only_dirty_panes(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    middle = tmp_path / "middle.txt"
    right = tmp_path / "right.txt"
    left.write_text("L\n", encoding="utf-8")
    middle.write_text("M\n", encoding="utf-8")
    right.write_text("R\n", encoding="utf-8")

    context = DiffContext(paths=[left, middle, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, middle, right])

    doc.update_pane_text(MergeDocument.LEFT, "L changed")
    doc.update_pane_text(MergeDocument.RIGHT, "R changed")

    saved_count = doc.save_all()

    assert saved_count == 2
    assert left.read_text(encoding="utf-8") == "L changed\n"
    assert middle.read_text(encoding="utf-8") == "M\n"
    assert right.read_text(encoding="utf-8") == "R changed\n"


def test_save_pane_preserves_crlf(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_bytes(b"A\r\nB\r\n")
    right.write_bytes(b"C\r\n")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])

    doc.update_pane_text(MergeDocument.LEFT, "A\nB\nC")

    ok = doc.save_pane(MergeDocument.LEFT)

    assert ok is True
    assert left.read_bytes() == b"A\r\nB\r\nC\r\n"


def test_save_pane_preserves_cp949(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_bytes("가\n나\n".encode("cp949"))
    right.write_text("x\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])

    doc.update_pane_text(MergeDocument.LEFT, "가\n다")

    ok = doc.save_pane(MergeDocument.LEFT)

    assert ok is True
    assert left.read_bytes() == "가\n다\n".encode("cp949")


def test_save_pane_as_writes_new_target_and_updates_backing_path(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    target = tmp_path / "saved-as.txt"
    left.write_text("L\n", encoding="utf-8")
    right.write_text("R\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])
    doc.update_pane_text(MergeDocument.LEFT, "L changed")

    ok = doc.save_pane_as(MergeDocument.LEFT, target)

    assert ok is True
    assert target.read_text(encoding="utf-8") == "L changed\n"
    assert doc.get_pane_path(MergeDocument.LEFT) == target
    assert doc.is_dirty(MergeDocument.LEFT) is False


def test_save_pane_as_preserves_existing_pane_format(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    target = tmp_path / "saved-as.txt"
    left.write_bytes("가\r\n나\r\n".encode("cp949"))
    right.write_text("x\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])
    doc.update_pane_text(MergeDocument.LEFT, "가\n다")

    ok = doc.save_pane_as(MergeDocument.LEFT, target)

    assert ok is True
    assert target.read_bytes() == "가\r\n다\r\n".encode("cp949")


def test_merge_doc_exposes_descriptions_and_modified_state(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("L\n", encoding="utf-8")
    right.write_text("R\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    states: list[bool] = []
    doc.modified_changed.connect(states.append)
    doc.open_docs([left, right])

    assert doc.get_description(MergeDocument.LEFT) == "left.txt"
    assert doc.get_description(MergeDocument.RIGHT) == "right.txt"
    assert doc.is_modified() is False

    doc.set_description(MergeDocument.LEFT, "Left Custom")
    doc.update_pane_text(MergeDocument.LEFT, "Changed")

    assert doc.get_description(MergeDocument.LEFT) == "Left Custom"
    assert doc.is_modified() is True
    assert states[-1] is True


def test_merge_doc_detects_disk_change_and_rescans(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("A\n", encoding="utf-8")
    right.write_text("B\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])

    left.write_text("A\nchanged-on-disk\n", encoding="utf-8")

    assert doc.check_pane_changed_on_disk(MergeDocument.LEFT) is True

    ok = doc.rescan_from_disk()

    assert ok is True
    assert doc.check_pane_changed_on_disk(MergeDocument.LEFT) is False
    assert "changed-on-disk" in doc.get_pane_text(MergeDocument.LEFT)


def test_merge_doc_exposes_format_and_mixed_eol(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_bytes(b"A\r\nB\n")
    right.write_text("R\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])

    fmt = doc.get_pane_format(MergeDocument.LEFT)

    assert fmt is not None
    assert fmt.newline == "\r\n"
    assert doc.is_mixed_eol(MergeDocument.LEFT) is True


# ---------------------------------------------------------------------------
# Word diff tests
# ---------------------------------------------------------------------------


def test_word_diff_array_returns_char_level_opcodes() -> None:
    from core.diff_context import DiffContext
    from core.diff_wrapper import DiffWrapper

    context = DiffContext(paths=[], compare_mode="text")
    wrapper = DiffWrapper(context)

    opcodes = wrapper.get_word_diff_array("hello world", "hello earth")
    # Should contain at least one non-equal op for the differing part
    ops = [op for op, *_ in opcodes]
    assert "replace" in ops or "insert" in ops or "delete" in ops
    equal_portions = [(i1, i2) for op, i1, i2, j1, j2 in opcodes if op == "equal"]
    # "hello " is shared
    assert any(i2 - i1 >= 6 for i1, i2 in equal_portions)


def test_merge_doc_get_word_diffs_for_lines(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("hello world\nfoo\n", encoding="utf-8")
    right.write_text("hello earth\nfoo\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    emitted: list = []
    doc.word_diffs_ready.connect(lambda pa, pb, data: emitted.append(data))
    doc.open_docs([left, right])

    result = doc.get_word_diffs_for_lines(MergeDocument.LEFT, MergeDocument.RIGHT, [0])

    assert len(result) == 1
    ops_line0 = [op for op, *_ in result[0]]
    assert "replace" in ops_line0 or "delete" in ops_line0 or "insert" in ops_line0
    assert len(emitted) == 1


# ---------------------------------------------------------------------------
# Partial line merge tests
# ---------------------------------------------------------------------------


def test_apply_merge_lines_copies_partial_range(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("A\nB\nC\nD\n", encoding="utf-8")
    right.write_text("W\nX\nY\nZ\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])

    # Copy lines 1-3 (B, C) from left into right
    ok = doc.apply_merge_lines(MergeDocument.LEFT, MergeDocument.RIGHT, 1, 3)

    assert ok is True
    assert doc.is_dirty(MergeDocument.RIGHT)
    right_lines = doc.get_pane_text(MergeDocument.RIGHT).splitlines()
    assert right_lines[1] == "B"
    assert right_lines[2] == "C"
    # Lines outside the range unchanged
    assert right_lines[0] == "W"
    assert right_lines[3] == "Z"


def test_apply_merge_lines_rejects_same_pane(tmp_path: Path) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("A\n", encoding="utf-8")
    right.write_text("B\n", encoding="utf-8")

    context = DiffContext(paths=[left, right], compare_mode="text")
    doc = MergeDocument(context)
    doc.open_docs([left, right])

    errors: list[str] = []
    doc.failed.connect(errors.append)
    ok = doc.apply_merge_lines(MergeDocument.LEFT, MergeDocument.LEFT, 0, 1)

    assert ok is False
    assert errors
