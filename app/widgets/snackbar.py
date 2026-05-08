from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton)
from PyQt6.QtCore import Qt, QTimer


class Snackbar(QFrame):
    """A Metro-style snackbar at the bottom of the window for undo notifications."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Snackbar")
        self.setStyleSheet("""
            QFrame#Snackbar {
                background-color: #333333;
                border-top: 1px solid #444;
            }
        """)
        self.setFixedHeight(50)
        self.hide()

        self._undo_callback = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)

        self.message_label = QLabel("")
        self.message_label.setStyleSheet("font-size: 14px; color: #FFFFFF;")
        layout.addWidget(self.message_label, stretch=1)

        self.undo_btn = QPushButton("UNDO")
        self.undo_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #00AEEF;
                border: none;
                font-size: 13px;
                font-weight: bold;
                padding: 5px 15px;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        self.undo_btn.clicked.connect(self._on_undo)
        layout.addWidget(self.undo_btn)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #AAAAAA;
                font-size: 14px;
            }
            QPushButton:hover { color: #FFFFFF; }
        """)
        close_btn.clicked.connect(self.hide)
        layout.addWidget(close_btn)

    def show_message(self, message, undo_callback=None, duration_ms=5000):
        self.message_label.setText(message)
        self._undo_callback = undo_callback
        self.undo_btn.setVisible(undo_callback is not None)
        self._timer.start(duration_ms)
        self.show()

    def _on_undo(self):
        if self._undo_callback:
            self._undo_callback()
        self.hide()
