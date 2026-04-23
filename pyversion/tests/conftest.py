from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

# Ensure imports like `from core...` resolve when tests are run from repo root.
PYVERSION_ROOT = Path(__file__).resolve().parents[1]
if str(PYVERSION_ROOT) not in sys.path:
    sys.path.insert(0, str(PYVERSION_ROOT))


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
