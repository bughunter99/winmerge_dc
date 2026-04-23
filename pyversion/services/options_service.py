from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OptionsService:
    ignore_case: bool = False
    ignore_whitespace: bool = False
    recursive: bool = True
