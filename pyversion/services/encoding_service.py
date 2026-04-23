from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def read_text_auto(path: Path) -> str:
    for enc in ("utf-8", "utf-16", "cp949", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class TextFileFormat:
    encoding: str
    newline: str
    mixed_eol: bool = False


def detect_text_format(path: Path) -> TextFileFormat:
    raw = path.read_bytes()

    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        encoding = "utf-16"
    else:
        encoding = _detect_encoding(raw)

    newline = _detect_newline(raw)
    return TextFileFormat(encoding=encoding, newline=newline, mixed_eol=_detect_mixed_eol(raw))


def _detect_encoding(raw: bytes) -> str:
    for enc in ("utf-8", "cp949", "latin-1"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _detect_newline(raw: bytes) -> str:
    if b"\r\n" in raw:
        return "\r\n"
    if b"\r" in raw:
        return "\r"
    return "\n"


def _detect_mixed_eol(raw: bytes) -> bool:
    has_crlf = b"\r\n" in raw
    stripped = raw.replace(b"\r\n", b"")
    has_lf = b"\n" in stripped
    has_cr = b"\r" in stripped
    return sum((has_crlf, has_lf, has_cr)) > 1
