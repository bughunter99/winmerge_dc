"""Tests for DiffWrapper multi-engine compare modes (quick / size / date / binary)."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from core.diff_context import DiffContext, DiffOptions
from core.diff_wrapper import DiffWrapper


def _make_wrapper(tmp_path: Path, method: str) -> tuple[DiffWrapper, Path, Path]:
    left = tmp_path / "left.bin"
    right = tmp_path / "right.bin"
    options = DiffOptions(compare_method=method)
    context = DiffContext(paths=[left, right], compare_mode="text", options=options)
    return DiffWrapper(context), left, right


def test_size_method_identical(tmp_path: Path) -> None:
    wrapper, left, right = _make_wrapper(tmp_path, "size")
    left.write_bytes(b"abcde")
    right.write_bytes(b"12345")  # same size, different content
    assert wrapper.run_file_diff(left, right) == 0  # size match → identical


def test_size_method_different(tmp_path: Path) -> None:
    wrapper, left, right = _make_wrapper(tmp_path, "size")
    left.write_bytes(b"abc")
    right.write_bytes(b"abcdef")
    assert wrapper.run_file_diff(left, right) == 1  # size mismatch


def test_quick_method_same_as_size(tmp_path: Path) -> None:
    wrapper, left, right = _make_wrapper(tmp_path, "quick")
    left.write_bytes(b"hello")
    right.write_bytes(b"hello")
    assert wrapper.run_file_diff(left, right) == 0


def test_binary_method_identical(tmp_path: Path) -> None:
    wrapper, left, right = _make_wrapper(tmp_path, "binary")
    left.write_bytes(b"\x00\x01\x02")
    right.write_bytes(b"\x00\x01\x02")
    assert wrapper.run_file_diff(left, right) == 0


def test_binary_method_different(tmp_path: Path) -> None:
    wrapper, left, right = _make_wrapper(tmp_path, "binary")
    left.write_bytes(b"\x00\x01\x02")
    right.write_bytes(b"\x00\x01\x03")
    assert wrapper.run_file_diff(left, right) == 1


def test_date_method_same_mtime(tmp_path: Path) -> None:
    wrapper, left, right = _make_wrapper(tmp_path, "date")
    left.write_bytes(b"aaa")
    right.write_bytes(b"bbb")
    # Force identical mtime
    t = time.time()
    import os
    os.utime(left, (t, t))
    os.utime(right, (t, t))
    assert wrapper.run_file_diff(left, right) == 0


def test_date_method_different_mtime(tmp_path: Path) -> None:
    wrapper, left, right = _make_wrapper(tmp_path, "date")
    left.write_bytes(b"aaa")
    right.write_bytes(b"bbb")
    import os
    t = time.time()
    os.utime(left, (t - 10, t - 10))
    os.utime(right, (t, t))
    assert wrapper.run_file_diff(left, right) == 1


def test_full_method_still_works(tmp_path: Path) -> None:
    wrapper, left, right = _make_wrapper(tmp_path, "full")
    left.write_text("line1\nline2\n", encoding="utf-8")
    right.write_text("line1\nLINE2\n", encoding="utf-8")
    assert wrapper.run_file_diff(left, right) == 1
