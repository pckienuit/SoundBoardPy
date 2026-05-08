from PyQt6.QtWidgets import (QPushButton, QMenu, QFileDialog, QInputDialog,
                             QColorDialog, QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QSlider, QDialogButtonBox)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import os
from app.audio_engine import audio_engine


class VolumeDialog(QDialog):
    """Dialog for adjusting volume offset of a sound button."""
    def __init__(self, current_offset=0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Volume Offset")
        self.setFixedSize(300, 160)
        self.offset = current_offset

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        layout.addWidget(QLabel("Adjust volume relative to default (0):"))

        slider_row = QHBoxLayout()
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(-10, 10)
        self.slider.setValue(current_offset)
        self.slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.slider.setTickInterval(1)

        self.value_label = QLabel(self._format(current_offset))
        self.value_label.setFixedWidth(40)
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet("color: #00AEEF; font-weight: bold; font-size: 14px;")

        self.slider.valueChanged.connect(lambda v: self.value_label.setText(self._format(v)))
        slider_row.addWidget(self.slider)
        slider_row.addWidget(self.value_label)
        layout.addLayout(slider_row)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self._accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _format(self, v):
        return f"+{v}" if v > 0 else str(v)

    def _accept(self):
        self.offset = self.slider.value()
        self.accept()


class SoundButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SoundButton")
        self.setText(" ")
        self.setAcceptDrops(True)
        self.setMinimumSize(80, 60)

        # State
        self.sound_name = ""
        self.sound_path = ""
        self.color = None          # QColor or None
        self.volume_offset = 0
        self.loop = False
        self.stop_all_sounds = False
        self.next_sound = ""

        self.is_selected = False
        self.stream_id = None
        self.is_playing = False
        self.is_paused = False

        self.clicked.connect(self.on_click)

    # -------------------------------------------------------------------------
    # Playback
    # -------------------------------------------------------------------------

    def on_click(self):
        if not self.sound_path or not os.path.exists(self.sound_path):
            return

        if self.is_playing:
            if self.is_paused:
                audio_engine.resume(self.stream_id)
                self.is_paused = False
                self._apply_playing_style()
            else:
                audio_engine.pause(self.stream_id)
                self.is_paused = True
                self._apply_paused_style()
        else:
            if self.stop_all_sounds:
                audio_engine.stop_all()

            self.stream_id = audio_engine.play(
                self.sound_path, loop=self.loop, volume_offset=self.volume_offset
            )
            if self.stream_id is not None:
                self.is_playing = True
                self.is_paused = False
                self._apply_playing_style()

    def stop(self):
        if self.stream_id is not None:
            audio_engine.stop(self.stream_id)
        self.is_playing = False
        self.is_paused = False
        self.stream_id = None
        self._apply_normal_style()

    def clear_button(self):
        self.stop()
        self.sound_name = ""
        self.sound_path = ""
        self.color = None
        self.volume_offset = 0
        self.loop = False
        self.stop_all_sounds = False
        self.next_sound = ""
        self.setText(" ")
        self._apply_normal_style()

    # -------------------------------------------------------------------------
    # Context Menu
    # -------------------------------------------------------------------------

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        action_choose = menu.addAction("Choose Sound")
        action_rename = menu.addAction("Rename")
        menu.addSeparator()
        action_color = menu.addAction("Set Color")
        action_volume = menu.addAction("Volume Offset")

        action_loop = menu.addAction("Loop")
        action_loop.setCheckable(True)
        action_loop.setChecked(self.loop)

        action_stop_all = menu.addAction("Stop All Sounds on Play")
        action_stop_all.setCheckable(True)
        action_stop_all.setChecked(self.stop_all_sounds)

        menu.addSeparator()
        action_clear = menu.addAction("Clear Button")

        action = menu.exec(event.globalPos())

        if action == action_choose:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "Select Audio File", "",
                "Audio Files (*.mp3 *.wav *.ogg *.flac *.m4a *.aac *.wma);;All Files (*.*)"
            )
            if file_path:
                self.set_sound(file_path)

        elif action == action_rename:
            new_name, ok = QInputDialog.getText(
                self, "Rename Sound", "New name:", text=self.sound_name
            )
            if ok and new_name:
                self.sound_name = new_name
                self.setText(new_name)

        elif action == action_color:
            initial = self.color if self.color else QColor("#3B3B3B")
            color = QColorDialog.getColor(initial, self, "Choose Button Color")
            if color.isValid():
                self.color = color
                self._apply_color(color)

        elif action == action_volume:
            dlg = VolumeDialog(self.volume_offset, parent=self)
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.volume_offset = dlg.offset

        elif action == action_loop:
            self.loop = not self.loop

        elif action == action_stop_all:
            self.stop_all_sounds = not self.stop_all_sounds

        elif action == action_clear:
            self.clear_button()

    # -------------------------------------------------------------------------
    # Drag & Drop
    # -------------------------------------------------------------------------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                path = urls[0].toLocalFile()
                audio_exts = ['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma']
                if any(path.lower().endswith(ext) for ext in audio_exts):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            self.set_sound(path)

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def set_sound(self, path, name=None):
        self.sound_path = path
        self.sound_name = name if name else os.path.splitext(os.path.basename(path))[0]
        self.setText(self.sound_name)

    def _apply_color(self, color: QColor):
        r, g, b = color.red(), color.green(), color.blue()
        # Determine text color based on background brightness
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        text_color = "#000000" if brightness > 128 else "#FFFFFF"
        self.setStyleSheet(
            f"QPushButton#SoundButton {{ background-color: rgb({r},{g},{b}); "
            f"color: {text_color}; border: 2px solid transparent; }}"
        )

    def _apply_playing_style(self):
        base = f"background-color: rgb({self.color.red()},{self.color.green()},{self.color.blue()});" if self.color else ""
        self.setStyleSheet(f"QPushButton#SoundButton {{ {base} border: 2px solid #00FF88; }}")

    def _apply_paused_style(self):
        base = f"background-color: rgb({self.color.red()},{self.color.green()},{self.color.blue()});" if self.color else ""
        self.setStyleSheet(f"QPushButton#SoundButton {{ {base} border: 2px solid #FFA500; }}")

    def _apply_normal_style(self):
        if self.color:
            self._apply_color(self.color)
        else:
            self.setStyleSheet("")
