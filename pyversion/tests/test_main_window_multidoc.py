"""Tests for MainWindow multi-doc routing, navigation, and conflict parsing."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from app.main_window import OpenRequest, _parse_conflict_markers


# ──────────────────────────────────────────────────────────────────────────────
# Conflict marker parser – no Qt needed
# ──────────────────────────────────────────────────────────────────────────────


def test_parse_conflict_markers_two_way() -> None:
    text = (
        "shared line\n"
        "<<<<<<< HEAD\n"
        "ours content\n"
        "=======\n"
        "theirs content\n"
        ">>>>>>> branch\n"
        "after\n"
    )
    ours, base, theirs = _parse_conflict_markers(text)

    assert "shared line" in ours
    assert "ours content" in ours
    assert "ours content" not in theirs
    assert "theirs content" in theirs
    assert "theirs content" not in ours
    assert "after" in ours
    assert "after" in theirs


def test_parse_conflict_markers_three_way() -> None:
    text = (
        "common\n"
        "<<<<<<< HEAD\n"
        "ours\n"
        "||||||| base\n"
        "base\n"
        "=======\n"
        "theirs\n"
        ">>>>>>> branch\n"
    )
    ours, base, theirs = _parse_conflict_markers(text)

    assert "ours" in ours
    assert "base" in base
    assert "theirs" in theirs
    # Ours should not contain base or theirs section
    assert "base" not in ours
    assert "theirs" not in ours


def test_parse_conflict_markers_no_conflict() -> None:
    text = "line1\nline2\nline3\n"
    ours, base, theirs = _parse_conflict_markers(text)
    # All three should be identical
    assert ours == base == theirs == text


# ──────────────────────────────────────────────────────────────────────────────
# OpenRequest – unit tests (no Qt)
# ──────────────────────────────────────────────────────────────────────────────


def test_open_request_defaults() -> None:
    req = OpenRequest(paths=[Path("/a"), Path("/b")])
    assert req.mode == "auto"
    assert req.descriptions == []


def test_open_request_with_descriptions() -> None:
    req = OpenRequest(paths=[Path("/a")], mode="conflict", descriptions=["Ours", "Base"])
    assert req.descriptions == ["Ours", "Base"]


# ──────────────────────────────────────────────────────────────────────────────
# MainWindow multi-doc and navigation – require QApplication
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(scope="module")
def main_window(qapp):
    from app.main_window import MainWindow
    from dataclasses import dataclass

    @dataclass
    class FakeConfig:
        compare_mode: str = "auto"

    win = MainWindow(FakeConfig())
    win.show()
    yield win


def test_open_targets_adds_tab(tmp_path: Path, main_window) -> None:
    left = tmp_path / "left.txt"
    right = tmp_path / "right.txt"
    left.write_text("A\n", encoding="utf-8")
    right.write_text("B\n", encoding="utf-8")

    main_window.open_targets(OpenRequest(paths=[left, right]))

    assert main_window._tab_widget.count() >= 1


def test_open_targets_adds_second_tab(tmp_path: Path, main_window) -> None:
    left1 = tmp_path / "l1.txt"
    right1 = tmp_path / "r1.txt"
    left2 = tmp_path / "l2.txt"
    right2 = tmp_path / "r2.txt"
    for f in (left1, right1, left2, right2):
        f.write_text("x\n", encoding="utf-8")

    before = main_window._tab_widget.count()
    main_window.open_targets(OpenRequest(paths=[left1, right1]))
    main_window.open_targets(OpenRequest(paths=[left2, right2]))

    assert main_window._tab_widget.count() == before + 2


def test_tab_title_contains_filenames(tmp_path: Path, main_window) -> None:
    left = tmp_path / "alpha.txt"
    right = tmp_path / "beta.txt"
    left.write_text("A\n", encoding="utf-8")
    right.write_text("B\n", encoding="utf-8")

    main_window.open_targets(OpenRequest(paths=[left, right]))
    last_idx = main_window._tab_widget.count() - 1
    title = main_window._tab_widget.tabText(last_idx)

    assert "alpha" in title
    assert "beta" in title


def test_navigate_actions_do_not_crash(tmp_path: Path, main_window) -> None:
    left = tmp_path / "nav_l.txt"
    right = tmp_path / "nav_r.txt"
    left.write_text("A\nB\nC\n", encoding="utf-8")
    right.write_text("A\nX\nC\n", encoding="utf-8")

    main_window.open_targets(OpenRequest(paths=[left, right]))

    # These should not raise even if no diff blocks exist in this 2-way doc
    main_window._on_navigate_first()
    main_window._on_navigate_next()
    main_window._on_navigate_prev()
    main_window._on_navigate_last()


def test_open_conflict_doc_creates_three_pane(tmp_path: Path, main_window) -> None:
    conflict = tmp_path / "conflict.txt"
    conflict.write_text(
        "shared\n<<<<<<< HEAD\nours\n=======\ntheirs\n>>>>>>> b\n",
        encoding="utf-8",
    )

    before = main_window._tab_widget.count()
    main_window._open_conflict_doc(conflict)

    assert main_window._tab_widget.count() == before + 1
    doc = main_window._active_merge_doc()
    assert doc is not None
    assert doc.is_three_way_mode()


def test_window_menu_lists_open_tabs(tmp_path: Path, main_window) -> None:
    left = tmp_path / "wm_l.txt"
    right = tmp_path / "wm_r.txt"
    left.write_text("A\n", encoding="utf-8")
    right.write_text("B\n", encoding="utf-8")

    main_window.open_targets(OpenRequest(paths=[left, right]))

    actions = main_window._window_menu.actions()
    assert len(actions) == main_window._tab_widget.count()


def test_modified_tab_gets_asterisk(tmp_path: Path, main_window) -> None:
    left = tmp_path / "mod_l.txt"
    right = tmp_path / "mod_r.txt"
    left.write_text("A\n", encoding="utf-8")
    right.write_text("B\n", encoding="utf-8")

    main_window.open_targets(OpenRequest(paths=[left, right]))
    idx = main_window._tab_widget.count() - 1
    doc = main_window._docs[idx].doc

    doc.update_pane_text(0, "DIRTY\n")

    title = main_window._tab_widget.tabText(idx)
    assert title.endswith(" *")
