from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class LocationViewWidget(QWidget):
    """Counterpart of CLocationView placeholder."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Location view placeholder"))
