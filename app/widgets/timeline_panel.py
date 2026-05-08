"""DJ-style timeline mixer panel for SoundBoardPy."""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QSlider, QProgressBar, QScrollArea, QSizePolicy,
    QToolButton, QFrame
)
from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter, QLinearGradient, QColor, QFont, QPen, QBrush
)


class VuMeterWidget(QWidget):
    """
    Compact horizontal VU meter for a single sound strip.
    Shows peak + RMS-style level bar using a gradient.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 12)
        self._level = 0.0

    def set_level(self, rms: float):
        """Update meter level from RMS (0.0 - 1.0)."""
        self._level = max(0.0, min(1.0, rms * 2.5))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        painter.setBrush(QColor("#1E1E1E"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, w, h, 2, 2)

        if self._level > 0.005:
            fill_w = int(w * self._level)
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor("#00AEEF"))
            grad.setColorAt(0.6, QColor("#00EF8B"))
            grad.setColorAt(0.85, QColor("#EFCF00"))
            grad.setColorAt(1.0, QColor("#EF3000"))
            painter.setBrush(grad)
            painter.drawRoundedRect(0, 0, fill_w, h, 2, 2)


class TimelineBar(QWidget):
    """
    Horizontal timeline progress bar showing playback position.
    Displays: name | progress bar | time elapsed / total
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(18)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._progress = 0.0   # 0.0 - 1.0
        self._is_fading = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._bar = QProgressBar()
        self._bar.setFixedHeight(10)
        self._bar.setTextVisible(False)
        self._bar.setRange(0, 1000)
        self._bar.setValue(0)

        self._time_label = QLabel("0:00 / 0:00")
        self._time_label.setStyleSheet("color: #AAAAAA; font-size: 10px;")
        self._time_label.setFixedWidth(90)
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(self._bar, 1)
        layout.addWidget(self._time_label)

    def set_progress(self, current: int, total: int, fs: int = 44100):
        """Update progress bar and time labels."""
        if total <= 0:
            self._progress = 0.0
            self._bar.setValue(0)
            self._time_label.setText("– : – – / – : – –")
            return

        self._progress = current / total
        self._bar.setValue(int(self._progress * 1000))

        cur_s = int(current / fs)
        tot_s = int(total / fs)
        self._time_label.setText(f"{_fmt_time(cur_s)} / {_fmt_time(tot_s)}")

    def set_fading(self, fading: bool):
        self._is_fading = fading
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)


class SoundStrip(QWidget):
    """
    A horizontal strip representing one active sound in the timeline panel.
    Contains: [expand?] name label | timeline bar | VU | volume indicator | stop button
    """

    stop_requested = pyqtSignal(int)   # stream_id

    def __init__(self, stream_id: int, name: str = "", parent=None):
        super().__init__(parent)
        self.stream_id = stream_id
        self.sound_name = name

        self.setObjectName("SoundStrip")
        self.setFixedHeight(56)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 2)
        layout.setSpacing(2)

        # Top row: name + controls
        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        self._name_label = QLabel(name or "Unknown")
        self._name_label.setObjectName("StripName")
        self._name_label.setFixedHeight(16)
        self._name_label.setToolTip(name or "Unknown")

        self._vol_label = QLabel("")
        self._vol_label.setObjectName("StripVol")
        self._vol_label.setFixedWidth(32)
        self._vol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._stop_btn = QPushButton("■")
        self._stop_btn.setObjectName("StripStop")
        self._stop_btn.setFixedSize(20, 20)
        self._stop_btn.setToolTip("Stop (fade-out)")
        self._stop_btn.clicked.connect(lambda: self.stop_requested.emit(self.stream_id))

        self._fade_label = QLabel("")
        self._fade_label.setObjectName("StripFade")
        self._fade_label.setFixedWidth(40)
        self._fade_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        top_row.addWidget(self._name_label, 1)
        top_row.addWidget(self._vol_label)
        top_row.addWidget(self._fade_label)
        top_row.addWidget(self._stop_btn)

        # Bottom row: timeline + VU
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(6)

        self._timeline = TimelineBar()
        self._vu = VuMeterWidget()

        bottom_row.addWidget(self._timeline, 1)
        bottom_row.addWidget(self._vu)

        layout.addLayout(top_row)
        layout.addLayout(bottom_row)

    def update_data(self, current_frame: int, total_frames: int, volume: float,
                    is_fading_out: bool, rms: float, fs: int = 44100,
                    volume_offset: int = 0):
        """Update strip display from latest stream data."""
        self._timeline.set_progress(current_frame, total_frames, fs)
        self._timeline.set_fading(is_fading_out)
        self._vu.set_level(rms)

        if volume_offset != 0:
            sign = "+" if volume_offset > 0 else ""
            self._vol_label.setText(f"{sign}{volume_offset}dB")
        else:
            self._vol_label.setText("")

        if is_fading_out:
            self._fade_label.setText("FADE")
            self._fade_label.setStyleSheet("color: #FFA500; font-size: 10px; font-weight: bold;")
        else:
            self._fade_label.setText("")
            self._fade_label.setStyleSheet("")

    def set_name(self, name: str):
        self.sound_name = name
        self._name_label.setText(name)


class TimelinePanel(QWidget):
    """
    Bottom DJ mixer panel showing active sounds as horizontal strips.
    Each strip has: name, timeline progress, VU meter, stop button.
    Global section: crossfade slider, fade-all button, collapse toggle.
    """

    # Emitted when user wants to stop a specific stream
    stream_stop_requested = pyqtSignal(int)    # stream_id
    # Emitted for global actions
    fade_all_requested = pyqtSignal()
    stop_all_requested = pyqtSignal()
    crossfade_changed = pyqtSignal(int)          # crossfade_ms

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TimelinePanel")
        self._collapsed = False
        self._strips = {}          # stream_id -> SoundStrip
        self._crossfade_ms = 300
        self._stream_fs = {}       # stream_id -> sample_rate (set externally via register_stream)

        # Track strip name + volume_offset per stream (for strip updates)
        self._stream_meta = {}     # stream_id -> {"name": str, "volume_offset": int, "fs": int}

        self._init_ui()
        self._init_timer()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Header bar ──────────────────────────────────────────────────────────
        header = QWidget()
        header.setObjectName("TimelineHeader")
        header.setFixedHeight(28)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 8, 0)
        header_layout.setSpacing(8)

        self._toggle_btn = QPushButton("▼ Timeline")
        self._toggle_btn.setObjectName("TimelineToggle")
        self._toggle_btn.setFixedHeight(20)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setChecked(True)
        self._toggle_btn.clicked.connect(self._toggle_collapse)

        header_layout.addWidget(self._toggle_btn)
        header_layout.addStretch(1)

        # Global controls
        global_label = QLabel("Crossfade:")
        global_label.setStyleSheet("color: #AAAAAA; font-size: 11px;")

        self._xf_slider = QSlider(Qt.Orientation.Horizontal)
        self._xf_slider.setObjectName("CrossfadeSlider")
        self._xf_slider.setRange(0, 2000)
        self._xf_slider.setValue(self._crossfade_ms)
        self._xf_slider.setFixedWidth(120)
        self._xf_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._xf_slider.setTickInterval(200)

        self._xf_val = QLabel(_fmt_ms(self._crossfade_ms))
        self._xf_val.setObjectName("CrossfadeVal")
        self._xf_val.setFixedWidth(40)

        self._xf_slider.valueChanged.connect(
            lambda v: self._xf_val.setText(_fmt_ms(v))
        )
        self._xf_slider.sliderReleased.connect(self._on_xf_changed)

        self._fade_all_btn = QPushButton("Fade All")
        self._fade_all_btn.setObjectName("FadeAllBtn")
        self._fade_all_btn.setFixedHeight(20)
        self._fade_all_btn.setToolTip("Fade out all sounds")
        self._fade_all_btn.clicked.connect(self.fade_all_requested.emit)

        self._stop_all_btn = QPushButton("Stop Now")
        self._stop_all_btn.setObjectName("StopAllBtn")
        self._stop_all_btn.setFixedHeight(20)
        self._stop_all_btn.setToolTip("Stop all sounds immediately (no fade)")
        self._stop_all_btn.clicked.connect(self.stop_all_requested.emit)

        header_layout.addWidget(global_label)
        header_layout.addWidget(self._xf_slider)
        header_layout.addWidget(self._xf_val)
        header_layout.addSpacing(8)
        header_layout.addWidget(self._fade_all_btn)
        header_layout.addWidget(self._stop_all_btn)

        main_layout.addWidget(header)

        # ── Strips area ─────────────────────────────────────────────────────────
        self._body = QWidget()
        self._body.setObjectName("TimelineBody")
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(4, 4, 4, 4)
        body_layout.setSpacing(4)

        self._strips_container = QWidget()
        self._strips_layout = QHBoxLayout(self._strips_container)
        self._strips_layout.setContentsMargins(0, 0, 0, 0)
        self._strips_layout.setSpacing(6)
        self._strips_layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setObjectName("TimelineScroll")
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(62)
        scroll.setWidget(self._strips_container)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body_layout.addWidget(scroll)

        main_layout.addWidget(self._body)

        self._update_body_visibility()

    def _init_timer(self):
        self._timer = QTimer(self)
        self._timer.setInterval(67)   # ~15 fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _tick(self):
        """Poll audio engine for active streams and update strips."""
        from app.audio_engine import audio_engine

        streams = audio_engine.get_playing_streams()
        active_ids = {s["stream_id"] for s in streams}

        # Remove strips for streams that are gone
        removed = set(self._strips.keys()) - active_ids
        for sid in removed:
            strip = self._strips.pop(sid, None)
            if strip:
                self._strips_layout.removeWidget(strip)
                strip.deleteLater()
                self._strips_layout.update()

        # Add new strips
        for s in streams:
            sid = s["stream_id"]
            if sid not in self._strips:
                meta = self._stream_meta.get(sid, {})
                name = meta.get("name", f"Sound {sid}")
                strip = SoundStrip(sid, name)
                strip.stop_requested.connect(self._on_strip_stop)
                self._strips[sid] = strip
                # Insert before the stretch
                self._strips_layout.insertWidget(self._strips_layout.count() - 1, strip)

        # Update existing strips
        for s in streams:
            sid = s["stream_id"]
            strip = self._strips.get(sid)
            if strip:
                meta = self._stream_meta.get(sid, {})
                fs = meta.get("fs", 44100)
                vol_offset = meta.get("volume_offset", 0)
                strip.update_data(
                    current_frame=s["current_frame"],
                    total_frames=s["total_frames"],
                    volume=s["volume"],
                    is_fading_out=s["is_fading_out"],
                    rms=audio_engine.get_stream_rms(sid),
                    fs=fs,
                    volume_offset=vol_offset,
                )

    def register_stream(self, stream_id: int, name: str = "", volume_offset: int = 0, fs: int = 44100):
        """Called by MainWindow to register a sound before it starts playing."""
        self._stream_meta[stream_id] = {
            "name": name,
            "volume_offset": volume_offset,
            "fs": fs,
        }

    def unregister_stream(self, stream_id: int):
        """Called when a stream is removed."""
        self._stream_meta.pop(stream_id, None)
        strip = self._strips.pop(stream_id, None)
        if strip:
            self._strips_layout.removeWidget(strip)
            strip.deleteLater()

    def _on_strip_stop(self, stream_id: int):
        self.stream_stop_requested.emit(stream_id)

    def _on_xf_changed(self):
        self._crossfade_ms = self._xf_slider.value()
        self.crossfade_changed.emit(self._crossfade_ms)

    def _toggle_collapse(self, checked: bool):
        self._collapsed = not checked
        self._update_body_visibility()
        self._toggle_btn.setText("▶ Timeline" if self._collapsed else "▼ Timeline")

    def _update_body_visibility(self):
        self._body.setVisible(not self._collapsed)

    def set_crossfade_ms(self, ms: int):
        self._crossfade_ms = ms
        self._xf_slider.setValue(ms)
        self._xf_val.setText(_fmt_ms(ms))

    def stop(self):
        self._timer.stop()

    def resume(self):
        if not self._timer.isActive():
            self._timer.start()


def _fmt_time(seconds: int) -> str:
    """Format seconds as M:SS."""
    if seconds < 0:
        return "–:––"
    m = seconds // 60
    s = seconds % 60
    return f"{m}:{s:02d}"


def _fmt_ms(ms: int) -> str:
    """Format milliseconds as '300ms' or '1.5s'."""
    if ms == 0:
        return "Off"
    if ms >= 1000:
        return f"{ms / 1000:.1f}s"
    return f"{ms}ms"
