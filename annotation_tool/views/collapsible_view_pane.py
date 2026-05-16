"""
Header bar with minimize/restore for a nested view (3D preview or 2D slice).
"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class CollapsibleViewPane(QWidget):
    """Wraps a content widget with a title bar and minimize/expand control."""

    collapse_changed = pyqtSignal(bool)  # True when collapsed

    HEADER_HEIGHT = 26
    COLLAPSED_SPLITTER_SIZE = 28

    def __init__(self, title: str, content: QWidget, parent=None):
        super().__init__(parent)
        self._title_text = title
        self._collapsed = False
        self._content = content

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QWidget()
        self._header.setFixedHeight(self.HEADER_HEIGHT)
        self._header.setStyleSheet(
            "background-color: #3a3a3a; border-bottom: 1px solid #555;"
        )
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(8, 2, 4, 2)

        self._title_label = QLabel(title)
        self._title_label.setStyleSheet("color: #ddd; font-weight: bold;")
        header_layout.addWidget(self._title_label)
        header_layout.addStretch()

        self._toggle_btn = QPushButton("−")
        self._toggle_btn.setFixedSize(26, 22)
        self._toggle_btn.setToolTip(f"Minimize {title}")
        self._toggle_btn.setStyleSheet(
            "QPushButton { background: #505050; color: #eee; border: 1px solid #666; }"
            "QPushButton:hover { background: #606060; }"
        )
        self._toggle_btn.clicked.connect(self.toggle)
        header_layout.addWidget(self._toggle_btn)

        layout.addWidget(self._header)
        layout.addWidget(self._content, 1)

        self._content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    @property
    def content(self) -> QWidget:
        return self._content

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    def toggle(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool, emit_signal: bool = True) -> None:
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self._content.setVisible(not collapsed)
        if collapsed:
            self._toggle_btn.setText("+")
            self._toggle_btn.setToolTip(f"Restore {self._title_text}")
        else:
            self._toggle_btn.setText("−")
            self._toggle_btn.setToolTip(f"Minimize {self._title_text}")
        if emit_signal:
            self.collapse_changed.emit(collapsed)
