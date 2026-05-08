"""Real-time stereo volume meter widget."""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QRectF
from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QFont


class VolumeMeterWidget(QWidget):
    """
    Compact horizontal RMS level meter.
    Reads RMS from the global audio_engine and draws a gradient bar.
    """
    _GRADIENT_STOPS = [
        (0.0,  QColor("#00AEEF")),
        (0.65, QColor("#00EF8B")),
        (0.85, QColor("#EFCF00")),
        (1.0,  QColor("#EF3000")),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 14)
        self.setToolTip("Master output level")

        self._level = 0.0      # 0.0 – 1.0 current draw level
        self._peak = 0.0       # peak hold
        self._peak_hold = 0    # frames to hold peak

        self._timer = QTimer(self)
        self._timer.setInterval(40)  # ~25 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ------------------------------------------------------------------

    def _tick(self):
        from app.audio_engine import audio_engine
        rms = audio_engine.get_master_rms()

        # Smooth decay
        target = min(rms * 3.0, 1.0)   # amplify for visual sensitivity
        if target >= self._level:
            self._level = target
        else:
            self._level = max(self._level - 0.04, 0.0)

        # Peak hold
        if self._level >= self._peak:
            self._peak = self._level
            self._peak_hold = 18   # hold ~720ms
        else:
            if self._peak_hold > 0:
                self._peak_hold -= 1
            else:
                self._peak = max(self._peak - 0.01, 0.0)

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()

        # Background track
        painter.setBrush(QColor("#1E1E1E"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, w, h, 3, 3)

        if self._level > 0.001:
            fill_w = int(w * self._level)
            grad = QLinearGradient(0, 0, w, 0)
            for stop, color in self._GRADIENT_STOPS:
                grad.setColorAt(stop, color)
            painter.setBrush(grad)
            painter.drawRoundedRect(0, 0, fill_w, h, 3, 3)

        # Peak marker
        if self._peak > 0.01:
            px = int(w * self._peak) - 2
            painter.setBrush(QColor("#FFFFFF"))
            painter.drawRect(px, 1, 2, h - 2)

        painter.end()

    def stop(self):
        self._timer.stop()

    def resume(self):
        self._timer.start()
