from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QSpinBox, QPushButton, QDialogButtonBox, QFrame)
from PyQt6.QtCore import Qt


class GridDialog(QDialog):
    """Dialog to configure the button grid (rows x columns)."""

    def __init__(self, current_rows=5, current_cols=2, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Change Button Grid")
        self.setModal(True)
        self.setFixedSize(300, 200)

        self.rows = current_rows
        self.cols = current_cols

        self._init_ui(current_rows, current_cols)

    def _init_ui(self, current_rows, current_cols):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Configure button grid size")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Rows
        row_layout = QHBoxLayout()
        row_label = QLabel("Rows:")
        row_label.setFixedWidth(80)
        self.row_spin = QSpinBox()
        self.row_spin.setRange(1, 20)
        self.row_spin.setValue(current_rows)
        self.row_spin.valueChanged.connect(self._update_preview)
        row_layout.addWidget(row_label)
        row_layout.addWidget(self.row_spin)
        layout.addLayout(row_layout)

        # Columns
        col_layout = QHBoxLayout()
        col_label = QLabel("Columns:")
        col_label.setFixedWidth(80)
        self.col_spin = QSpinBox()
        self.col_spin.setRange(1, 20)
        self.col_spin.setValue(current_cols)
        self.col_spin.valueChanged.connect(self._update_preview)
        col_layout.addWidget(col_label)
        col_layout.addWidget(self.col_spin)
        layout.addLayout(col_layout)

        # Preview label
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("color: #00AEEF; font-size: 12px;")
        layout.addWidget(self.preview_label)
        self._update_preview()

        # Buttons
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _update_preview(self):
        r = self.row_spin.value()
        c = self.col_spin.value()
        total = r * c
        warn = " ⚠️ Large grid!" if total > 300 else ""
        self.preview_label.setText(f"{r} rows × {c} cols = {total} buttons{warn}")

    def _on_accept(self):
        self.rows = self.row_spin.value()
        self.cols = self.col_spin.value()
        self.accept()
