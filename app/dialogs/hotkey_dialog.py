from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFrame, QDialogButtonBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeySequence


_MODIFIER_MAP = {
    Qt.Key.Key_Control: "ctrl",
    Qt.Key.Key_Shift:   "shift",
    Qt.Key.Key_Alt:     "alt",
    Qt.Key.Key_Meta:    "windows",
}

_SPECIAL_KEY_MAP = {
    Qt.Key.Key_F1: "f1", Qt.Key.Key_F2: "f2", Qt.Key.Key_F3: "f3",
    Qt.Key.Key_F4: "f4", Qt.Key.Key_F5: "f5", Qt.Key.Key_F6: "f6",
    Qt.Key.Key_F7: "f7", Qt.Key.Key_F8: "f8", Qt.Key.Key_F9: "f9",
    Qt.Key.Key_F10: "f10", Qt.Key.Key_F11: "f11", Qt.Key.Key_F12: "f12",
    Qt.Key.Key_Space: "space", Qt.Key.Key_Return: "enter",
    Qt.Key.Key_Enter: "enter", Qt.Key.Key_Escape: "esc",
    Qt.Key.Key_Backspace: "backspace", Qt.Key.Key_Delete: "delete",
    Qt.Key.Key_Insert: "insert", Qt.Key.Key_Home: "home",
    Qt.Key.Key_End: "end", Qt.Key.Key_PageUp: "page up",
    Qt.Key.Key_PageDown: "page down", Qt.Key.Key_Tab: "tab",
    Qt.Key.Key_Up: "up", Qt.Key.Key_Down: "down",
    Qt.Key.Key_Left: "left", Qt.Key.Key_Right: "right",
}


class HotkeyPickerDialog(QDialog):
    """Dialog to capture and assign a global hotkey combination to a button."""

    def __init__(self, current_hotkey="", existing_hotkeys=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Hotkey")
        self.setFixedSize(380, 220)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.hotkey = current_hotkey
        self._existing = existing_hotkeys or []
        self._capturing = False
        self._captured = ""

        self._build_ui()
        self._update_display()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)

        # Instruction label
        lbl_inst = QLabel("Press the key combination you want to assign:")
        lbl_inst.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        layout.addWidget(lbl_inst)

        # Key display frame
        self._frame = QFrame()
        self._frame.setObjectName("HotkeyFrame")
        self._frame.setFixedHeight(56)
        self._frame.setStyleSheet("""
            QFrame#HotkeyFrame {
                background-color: #1A1A1A;
                border: 2px solid #444444;
                border-radius: 4px;
            }
            QFrame#HotkeyFrame[capturing="true"] {
                border: 2px solid #00AEEF;
            }
        """)
        frame_layout = QHBoxLayout(self._frame)
        frame_layout.setContentsMargins(12, 0, 12, 0)

        self._lbl_key = QLabel("Click here to capture…")
        self._lbl_key.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_key.setStyleSheet("color: #666666; font-size: 15px; font-weight: bold;")
        frame_layout.addWidget(self._lbl_key)
        layout.addWidget(self._frame)

        # Status / conflict label
        self._lbl_status = QLabel("")
        self._lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_status.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._lbl_status)

        layout.addStretch()

        # Buttons row
        btn_row = QHBoxLayout()
        self._btn_capture = QPushButton("▶  Start Capture")
        self._btn_capture.setObjectName("PrimaryBtn")
        self._btn_capture.setStyleSheet("""
            QPushButton#PrimaryBtn {
                background-color: #00AEEF; color: #000;
                border: none; border-radius: 3px; padding: 6px 18px; font-weight: bold;
            }
            QPushButton#PrimaryBtn:hover { background-color: #33BFFF; }
        """)
        self._btn_capture.clicked.connect(self._toggle_capture)

        self._btn_clear = QPushButton("✕  Clear")
        self._btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #3B3B3B; color: #CCC;
                border: none; border-radius: 3px; padding: 6px 14px;
            }
            QPushButton:hover { background-color: #555; }
        """)
        self._btn_clear.clicked.connect(self._clear_hotkey)

        btn_row.addWidget(self._btn_capture)
        btn_row.addWidget(self._btn_clear)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # OK / Cancel
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                               QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self._on_ok)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    # ── Capture Logic ────────────────────────────────────────────────────────

    def _toggle_capture(self):
        if self._capturing:
            self._stop_capture()
        else:
            self._start_capture()

    def _start_capture(self):
        self._capturing = True
        self._captured = ""
        self._frame.setProperty("capturing", "true")
        self._frame.style().unpolish(self._frame)
        self._frame.style().polish(self._frame)
        self._lbl_key.setText("Listening…")
        self._lbl_key.setStyleSheet("color: #00AEEF; font-size: 15px; font-weight: bold;")
        self._btn_capture.setText("⏹  Stop Capture")
        self._lbl_status.setText("")
        self.setFocus()

    def _stop_capture(self):
        self._capturing = False
        self._frame.setProperty("capturing", "false")
        self._frame.style().unpolish(self._frame)
        self._frame.style().polish(self._frame)
        self._btn_capture.setText("▶  Start Capture")
        if self._captured:
            self.hotkey = self._captured
        self._update_display()

    def _clear_hotkey(self):
        self._capturing = False
        self._captured = ""
        self.hotkey = ""
        self._btn_capture.setText("▶  Start Capture")
        self._update_display()

    def keyPressEvent(self, event):
        if not self._capturing:
            super().keyPressEvent(event)
            return

        key = event.key()
        # Ignore pure modifiers
        if key in _MODIFIER_MAP:
            return

        # Build combo string
        parts = []
        mods = event.modifiers()
        if mods & Qt.KeyboardModifier.ControlModifier:
            parts.append("ctrl")
        if mods & Qt.KeyboardModifier.AltModifier:
            parts.append("alt")
        if mods & Qt.KeyboardModifier.ShiftModifier:
            parts.append("shift")
        if mods & Qt.KeyboardModifier.MetaModifier:
            parts.append("windows")

        if key in _SPECIAL_KEY_MAP:
            parts.append(_SPECIAL_KEY_MAP[key])
        else:
            char = event.text().lower()
            if char and char.isprintable():
                parts.append(char)
            else:
                return  # Unknown key, ignore

        combo = "+".join(parts)
        if combo:
            self._captured = combo
            self._lbl_key.setText(self._format_display(combo))
            self._lbl_key.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold;")
            self._stop_capture()

    def _format_display(self, combo):
        """Convert 'ctrl+alt+a' → 'Ctrl + Alt + A' for display."""
        if not combo:
            return "None"
        return "  +  ".join(p.capitalize() for p in combo.split("+"))

    def _update_display(self):
        if self.hotkey:
            self._lbl_key.setText(self._format_display(self.hotkey))
            self._lbl_key.setStyleSheet("color: #FFFFFF; font-size: 15px; font-weight: bold;")
        else:
            self._lbl_key.setText("No hotkey assigned")
            self._lbl_key.setStyleSheet("color: #666666; font-size: 15px; font-weight: bold;")
        self._check_conflict()

    def _check_conflict(self):
        if not self.hotkey:
            self._lbl_status.setText("")
            return
        if self.hotkey in self._existing:
            self._lbl_status.setText(f"⚠  This hotkey is already used by another button!")
            self._lbl_status.setStyleSheet("color: #FFA500; font-size: 11px;")
        else:
            self._lbl_status.setText(f"✓  Hotkey is available")
            self._lbl_status.setStyleSheet("color: #00CC77; font-size: 11px;")

    def _on_ok(self):
        self.accept()
