"""Audio Passthrough dialog — route microphone input to output device."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QComboBox, QFrame, QSlider
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


class PassthroughDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Audio Passthrough")
        self.setFixedSize(440, 320)
        self.setModal(False)
        self._active = False
        self._build_ui()
        self._populate_devices()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        title = QLabel("🎙  Audio Passthrough")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #444;")
        layout.addWidget(line)

        desc = QLabel("Routes microphone to the selected output device in real-time.")
        desc.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        layout.addWidget(desc)

        for label_text, attr in [("Input Device:", "combo_input"), ("Output Device:", "combo_output")]:
            row = QHBoxLayout()
            lbl = QLabel(label_text)
            lbl.setFixedWidth(110)
            combo = QComboBox()
            setattr(self, attr, combo)
            row.addWidget(lbl)
            row.addWidget(combo)
            layout.addLayout(row)

        gain_row = QHBoxLayout()
        gain_row.addWidget(QLabel("Gain:"))
        self.slider_gain = QSlider(Qt.Orientation.Horizontal)
        self.slider_gain.setRange(0, 200)
        self.slider_gain.setValue(100)
        self.gain_lbl = QLabel("100%")
        self.gain_lbl.setStyleSheet("color: #00AEEF; font-weight: bold;")
        self.slider_gain.valueChanged.connect(lambda v: self.gain_lbl.setText(f"{v}%"))
        gain_row.addWidget(self.slider_gain)
        gain_row.addWidget(self.gain_lbl)
        layout.addLayout(gain_row)

        layout.addStretch()

        self.status_label = QLabel("● Stopped")
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.status_label)

        btn_row = QHBoxLayout()
        self.btn_toggle = QPushButton("▶  Start Passthrough")
        self.btn_close = QPushButton("Close")
        self.btn_toggle.setMinimumHeight(36)
        self.btn_toggle.setStyleSheet(
            "QPushButton{background:#00AEEF;color:#000;border:none;border-radius:3px;"
            "font-weight:bold;padding:0 16px;}"
            "QPushButton:hover{background:#33C4FF;}"
        )
        self.btn_close.setMinimumHeight(36)
        self.btn_close.setStyleSheet(
            "QPushButton{background:#3B3B3B;color:#CCC;border:none;border-radius:3px;padding:0 16px;}"
            "QPushButton:hover{background:#555;}"
        )
        self.btn_toggle.clicked.connect(self._toggle_passthrough)
        self.btn_close.clicked.connect(self._on_close)
        btn_row.addWidget(self.btn_toggle)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

    def _populate_devices(self):
        from app.audio_engine import audio_engine
        devices = audio_engine.get_devices()
        self._input_ids, self._output_ids = [], []
        self.combo_input.clear()
        self.combo_output.clear()
        for idx, dev in enumerate(devices):
            if dev["max_input_channels"] > 0:
                self.combo_input.addItem(dev["name"])
                self._input_ids.append(idx)
            if dev["max_output_channels"] > 0:
                self.combo_output.addItem(dev["name"])
                self._output_ids.append(idx)

    def _toggle_passthrough(self):
        from app.audio_engine import audio_engine
        if self._active:
            audio_engine.stop_passthrough()
            self._active = False
            self.btn_toggle.setText("▶  Start Passthrough")
            self.btn_toggle.setStyleSheet(
                "QPushButton{background:#00AEEF;color:#000;border:none;border-radius:3px;"
                "font-weight:bold;padding:0 16px;}"
            )
            self.status_label.setText("● Stopped")
            self.status_label.setStyleSheet("color:#666;font-size:12px;")
            self.combo_input.setEnabled(True)
            self.combo_output.setEnabled(True)
        else:
            in_idx = self._input_ids[self.combo_input.currentIndex()] if self._input_ids else None
            out_idx = self._output_ids[self.combo_output.currentIndex()] if self._output_ids else None
            if in_idx is None or out_idx is None:
                return
            gain = self.slider_gain.value() / 100.0
            ok = audio_engine.start_passthrough(in_idx, out_idx, gain=gain)
            if ok:
                self._active = True
                self.btn_toggle.setText("⏹  Stop Passthrough")
                self.btn_toggle.setStyleSheet(
                    "QPushButton{background:#EF3000;color:#FFF;border:none;border-radius:3px;"
                    "font-weight:bold;padding:0 16px;}"
                )
                self.status_label.setText("● Live — routing audio…")
                self.status_label.setStyleSheet("color:#00FF88;font-size:12px;font-weight:bold;")
                self.combo_input.setEnabled(False)
                self.combo_output.setEnabled(False)

    def _on_close(self):
        if self._active:
            from app.audio_engine import audio_engine
            audio_engine.stop_passthrough()
            self._active = False
        self.accept()

    def closeEvent(self, event):
        if self._active:
            from app.audio_engine import audio_engine
            audio_engine.stop_passthrough()
        super().closeEvent(event)
