from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow


@dataclass
class AppConfig:
    compare_mode: str = "auto"
    no_prefs: bool = False


class MergeApplication:
    """Python counterpart of WinMerge CMergeApp."""

    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self.config = self._parse_args(argv)
        self.qt_app = QApplication(argv)
        self.main_window = MainWindow(app_config=self.config)

    def _parse_args(self, argv: list[str]) -> AppConfig:
        parser = argparse.ArgumentParser(prog="winmerge-py")
        parser.add_argument("--compare-mode", default="auto", choices=["auto", "text", "folder", "binary", "image"])
        parser.add_argument("--no-prefs", action="store_true")
        args = parser.parse_args(argv[1:])
        return AppConfig(compare_mode=args.compare_mode, no_prefs=args.no_prefs)

    def init_instance(self) -> int:
        self.main_window.show()
        return self.qt_app.exec()


def run() -> int:
    app = MergeApplication(sys.argv)
    return app.init_instance()
