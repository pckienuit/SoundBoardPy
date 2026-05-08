from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QPushButton, QLabel
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut


class SearchPanel(QWidget):
    """
    A collapsible search bar that filters SoundButtons across all tabs.
    Activate with Ctrl+F or the toolbar search button.
    """

    # Emits (query_str) when the search query changes
    search_changed = pyqtSignal(str)
    # Emits when the panel is closed
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SearchPanel")
        self.setFixedHeight(44)
        self.hide()
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(8)

        # Search icon label
        icon_lbl = QLabel("🔍")
        icon_lbl.setFixedWidth(22)
        icon_lbl.setStyleSheet("font-size: 14px; background: transparent;")
        layout.addWidget(icon_lbl)

        # Input field
        self._input = QLineEdit()
        self._input.setObjectName("SearchInput")
        self._input.setPlaceholderText("Search sounds across all tabs…")
        self._input.setClearButtonEnabled(True)
        self._input.textChanged.connect(self._on_text_changed)
        self._input.returnPressed.connect(self._next_result)
        layout.addWidget(self._input)

        # Result counter
        self._lbl_count = QLabel("")
        self._lbl_count.setObjectName("SearchCount")
        self._lbl_count.setFixedWidth(90)
        self._lbl_count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_count.setStyleSheet("color: #888; font-size: 11px; background: transparent;")
        layout.addWidget(self._lbl_count)

        # Prev / Next navigation
        self._btn_prev = QPushButton("▲")
        self._btn_next = QPushButton("▼")
        for btn in (self._btn_prev, self._btn_next):
            btn.setFixedSize(26, 26)
            btn.setStyleSheet("""
                QPushButton {
                    background: #3B3B3B; color: #CCC;
                    border: none; border-radius: 3px; font-size: 10px;
                }
                QPushButton:hover { background: #555; }
                QPushButton:disabled { color: #555; }
            """)
        self._btn_prev.clicked.connect(self._prev_result)
        self._btn_next.clicked.connect(self._next_result)
        layout.addWidget(self._btn_prev)
        layout.addWidget(self._btn_next)

        # Close button
        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setToolTip("Close search (Esc)")
        btn_close.setStyleSheet("""
            QPushButton {
                background: transparent; color: #888;
                border: none; font-size: 13px;
            }
            QPushButton:hover { color: #FFF; }
        """)
        btn_close.clicked.connect(self.close_panel)
        layout.addWidget(btn_close)

    # ── Public API ──────────────────────────────────────────────────────────

    def open_panel(self):
        """Show panel and focus the input."""
        self.show()
        self._input.setFocus()
        self._input.selectAll()

    def close_panel(self):
        """Hide panel, clear highlights, emit closed signal."""
        self._input.clear()
        self.hide()
        self.closed.emit()

    def set_result_info(self, found: int, current: int):
        """Update the result counter label."""
        if found == 0:
            self._lbl_count.setText("No results")
            self._lbl_count.setStyleSheet("color: #FF6666; font-size: 11px; background: transparent;")
        else:
            self._lbl_count.setText(f"{current}/{found}")
            self._lbl_count.setStyleSheet("color: #00CC77; font-size: 11px; background: transparent;")
        self._btn_prev.setEnabled(found > 1)
        self._btn_next.setEnabled(found > 1)

    def clear_result_info(self):
        self._lbl_count.setText("")
        self._btn_prev.setEnabled(False)
        self._btn_next.setEnabled(False)

    # ── Internal ────────────────────────────────────────────────────────────

    def _on_text_changed(self, text):
        self.search_changed.emit(text.strip())
        if not text.strip():
            self.clear_result_info()

    def _next_result(self):
        # Trigger next navigation — handled by MainWindow
        self.search_changed.emit(f"__nav_next__{self._input.text().strip()}")

    def _prev_result(self):
        self.search_changed.emit(f"__nav_prev__{self._input.text().strip()}")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close_panel()
        else:
            super().keyPressEvent(event)
