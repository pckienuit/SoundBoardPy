from PyQt6.QtWidgets import (QPushButton, QMenu, QFileDialog, QInputDialog,
                             QColorDialog, QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QSlider, QDialogButtonBox, QComboBox,
                             QGroupBox, QFormLayout)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QIcon
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


class FadeDialog(QDialog):
    """
    Dialog for configuring fade-in, fade-out, fade mode, and crossfade duration
    for a sound button.
    """
    def __init__(self, current_fade_in=0, current_fade_out=0,
                 current_fade_mode="auto", current_crossfade=0,
                 sound_name="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fade Settings")
        self.setFixedSize(380, 370)

        self.fade_in = current_fade_in
        self.fade_out = current_fade_out
        self.fade_mode = current_fade_mode
        self.crossfade = current_crossfade

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        # Header
        name_label = QLabel(f"<b>Fade Settings</b>  –  {sound_name or 'Untitled'}")
        name_label.setStyleSheet("color: #00AEEF;")
        layout.addWidget(name_label)

        # ── Fade In ────────────────────────────────────────────────────────────
        in_group = QGroupBox("Fade In")
        in_layout = QVBoxLayout(in_group)
        in_layout.setSpacing(8)

        in_row = QHBoxLayout()
        in_row.addWidget(QLabel("Duration:"))
        self.in_slider = QSlider(Qt.Orientation.Horizontal)
        self.in_slider.setRange(0, 5000)
        self.in_slider.setValue(current_fade_in)
        self.in_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.in_slider.setTickInterval(500)
        self.in_val = QLabel(self._ms(current_fade_in))
        self.in_val.setFixedWidth(55)
        self.in_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.in_val.setStyleSheet("color: #00AEEF; font-weight: bold; font-size: 13px;")
        self.in_slider.valueChanged.connect(lambda v: self.in_val.setText(self._ms(v)))
        in_row.addWidget(self.in_slider)
        in_row.addWidget(self.in_val)
        in_layout.addLayout(in_row)

        in_note = QLabel("Volume ramps from 0 to full over this duration when the sound starts.")
        in_note.setStyleSheet("color: #888; font-size: 11px;")
        in_layout.addWidget(in_note)
        layout.addWidget(in_group)

        # ── Fade Out ───────────────────────────────────────────────────────────
        out_group = QGroupBox("Fade Out")
        out_layout = QVBoxLayout(out_group)
        out_layout.setSpacing(8)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("Duration:"))
        self.out_slider = QSlider(Qt.Orientation.Horizontal)
        self.out_slider.setRange(0, 5000)
        self.out_slider.setValue(current_fade_out)
        self.out_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.out_slider.setTickInterval(500)
        self.out_val = QLabel(self._ms(current_fade_out))
        self.out_val.setFixedWidth(55)
        self.out_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.out_val.setStyleSheet("color: #00AEEF; font-weight: bold; font-size: 13px;")
        self.out_slider.valueChanged.connect(lambda v: self.out_val.setText(self._ms(v)))
        out_row.addWidget(self.out_slider)
        out_row.addWidget(self.out_val)
        out_layout.addLayout(out_row)

        out_note = QLabel("Volume ramps to 0 when the sound stops naturally or is clicked to stop.")
        out_note.setStyleSheet("color: #888; font-size: 11px;")
        out_layout.addWidget(out_note)
        layout.addWidget(out_group)

        # ── Fade Mode ──────────────────────────────────────────────────────────
        mode_group = QGroupBox("Fade Mode")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(6)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Auto – always fade in & fade out",
            "On Stop Only – fade only when stopped",
            "On Click Only – fade only when clicked to stop",
        ])
        mode_map = {
            "auto": 0,
            "on_stop_only": 1,
            "on_click": 2,
        }
        self.mode_combo.setCurrentIndex(mode_map.get(current_fade_mode, 0))

        mode_note = QLabel(
            "Auto: fade in on play, fade out on stop. "
            "On Stop Only: fade out only at end-of-file. "
            "On Click Only: fade out only when user clicks button."
        )
        mode_note.setWordWrap(True)
        mode_note.setStyleSheet("color: #888; font-size: 11px;")

        mode_layout.addWidget(self.mode_combo)
        mode_layout.addWidget(mode_note)
        layout.addWidget(mode_group)

        # ── Crossfade Duration ──────────────────────────────────────────────────
        xf_group = QGroupBox("Crossfade")
        xf_layout = QVBoxLayout(xf_group)
        xf_layout.setSpacing(8)

        xf_row = QHBoxLayout()
        xf_row.addWidget(QLabel("Duration:"))
        self.xf_slider = QSlider(Qt.Orientation.Horizontal)
        self.xf_slider.setRange(0, 2000)
        self.xf_slider.setValue(current_crossfade)
        self.xf_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.xf_slider.setTickInterval(200)
        self.xf_val = QLabel(self._ms(current_crossfade))
        self.xf_val.setFixedWidth(55)
        self.xf_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.xf_val.setStyleSheet("color: #00AEEF; font-weight: bold; font-size: 13px;")
        self.xf_slider.valueChanged.connect(lambda v: self.xf_val.setText(self._ms(v)))
        xf_row.addWidget(self.xf_slider)
        xf_row.addWidget(self.xf_val)
        xf_layout.addLayout(xf_row)

        xf_note = QLabel(
            "When this button plays (and 'Stop All on Play' is enabled), "
            "other sounds fade out over this duration while this sound fades in."
        )
        xf_note.setWordWrap(True)
        xf_note.setStyleSheet("color: #888; font-size: 11px;")
        xf_layout.addWidget(xf_note)
        layout.addWidget(xf_group)

        # ── Buttons ────────────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _ms(self, v):
        if v == 0:
            return "Off"
        if v >= 1000:
            return f"{v / 1000:.1f}s"
        return f"{v}ms"

    def _accept(self):
        self.fade_in = self.in_slider.value()
        self.fade_out = self.out_slider.value()
        mode_keys = ["auto", "on_stop_only", "on_click"]
        self.fade_mode = mode_keys[self.mode_combo.currentIndex()]
        self.crossfade = self.xf_slider.value()
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
        self.icon_path = ""
        self.color = None
        self.volume_offset = 0
        self.loop = False
        self.stop_all_sounds = False
        self.next_sound = ""
        self.hotkey = ""

        # Fade / crossfade settings
        self.fade_in_duration = 0       # ms, 0 = no fade-in
        self.fade_out_duration = 0      # ms, 0 = no fade-out
        self.fade_mode = "auto"          # "auto" | "on_stop_only" | "on_click"
        self.crossfade_duration = 0      # ms, crossfade with other sounds

        self.is_selected = False
        self.stream_id = None
        self.is_playing = False
        self.is_paused = False

        # Search highlight state
        self._search_highlighted = False

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
                self._stop_sound(triggered_by="click")
        else:
            self._start_sound()

    def _start_sound(self):
        """Start playback with fade-in if configured."""
        if self.stop_all_sounds and self.crossfade_duration > 0:
            # Crossfade: fade out all other streams, then fade-in this one
            old_streams = audio_engine.get_playing_streams()
            for s in old_streams:
                audio_engine.crossfade(s["stream_id"], -1, self.crossfade_duration)
        elif self.stop_all_sounds:
            audio_engine.stop_all()

        self.stream_id = audio_engine.play(
            self.sound_path,
            loop=self.loop,
            volume_offset=self.volume_offset,
            fade_in_ms=self.fade_in_duration if self.fade_mode == "auto" else 0,
        )
        if self.stream_id is not None:
            self.is_playing = True
            self.is_paused = False
            self._apply_playing_style()

    def _stop_sound(self, triggered_by="click"):
        """
        Stop playback, applying fade-out based on fade_mode.

        triggered_by: "click" | "end" | "silence"
        """
        if self.stream_id is None:
            return

        use_fade = False
        if self.fade_mode == "auto":
            use_fade = True
        elif self.fade_mode == "on_click" and triggered_by == "click":
            use_fade = True
        elif self.fade_mode == "on_stop_only" and triggered_by == "end":
            use_fade = True

        if use_fade and self.fade_out_duration > 0:
            audio_engine.fade_out(self.stream_id, duration_ms=self.fade_out_duration)
        else:
            audio_engine.stop(self.stream_id)
            self.is_playing = False
            self.is_paused = False
            self.stream_id = None
            self._apply_normal_style()

    def stop(self):
        """Public stop method – fade-out if configured."""
        if self.stream_id is None:
            return
        self._stop_sound(triggered_by="click")

    def clear_button(self):
        if self.stream_id is not None:
            audio_engine.stop(self.stream_id)
        self._unregister_hotkey()
        self.sound_name = ""
        self.sound_path = ""
        self.icon_path = ""
        self.color = None
        self.volume_offset = 0
        self.loop = False
        self.stop_all_sounds = False
        self.next_sound = ""
        self.hotkey = ""
        self.fade_in_duration = 0
        self.fade_out_duration = 0
        self.fade_mode = "auto"
        self.crossfade_duration = 0
        self.is_playing = False
        self.is_paused = False
        self.stream_id = None
        self.setText(" ")
        self.setIcon(QIcon())
        self.setIconSize(QSize(0, 0))
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
        action_fade = menu.addAction("Fade Settings…")

        action_loop = menu.addAction("Loop")
        action_loop.setCheckable(True)
        action_loop.setChecked(self.loop)

        action_stop_all = menu.addAction("Stop All Sounds on Play")
        action_stop_all.setCheckable(True)
        action_stop_all.setChecked(self.stop_all_sounds)

        menu.addSeparator()
        action_icon = menu.addAction("Set Icon…")
        if self.icon_path:
            action_clear_icon = menu.addAction("Clear Icon")
        else:
            action_clear_icon = None
        menu.addSeparator()
        hotkey_label = f"Set Hotkey  [{self.hotkey}]" if self.hotkey else "Set Hotkey…"
        action_hotkey = menu.addAction(hotkey_label)
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

        elif action == action_fade:
            dlg = FadeDialog(
                current_fade_in=self.fade_in_duration,
                current_fade_out=self.fade_out_duration,
                current_fade_mode=self.fade_mode,
                current_crossfade=self.crossfade_duration,
                sound_name=self.sound_name or "Untitled",
                parent=self
            )
            if dlg.exec() == QDialog.DialogCode.Accepted:
                self.fade_in_duration = dlg.fade_in
                self.fade_out_duration = dlg.fade_out
                self.fade_mode = dlg.fade_mode
                self.crossfade_duration = dlg.crossfade

        elif action == action_loop:
            self.loop = not self.loop

        elif action == action_stop_all:
            self.stop_all_sounds = not self.stop_all_sounds

        elif action == action_icon:
            self._pick_icon()

        elif action_clear_icon and action == action_clear_icon:
            self._clear_icon()

        elif action == action_hotkey:
            self._pick_hotkey()

        elif action == action_clear:
            self.clear_button()

    # -------------------------------------------------------------------------
    # Icon
    # -------------------------------------------------------------------------

    def _pick_icon(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Icon Image", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.svg *.ico);;All Files (*.*)"
        )
        if path:
            self.icon_path = path
            self._apply_icon()

    def _clear_icon(self):
        self.icon_path = ""
        self.setIcon(QIcon())
        self.setIconSize(QSize(0, 0))
        self.setText(self.sound_name if self.sound_name else " ")

    def _apply_icon(self):
        if self.icon_path and os.path.exists(self.icon_path):
            icon = QIcon(self.icon_path)
            self.setIcon(icon)
            btn_h = self.height() or 60
            icon_sz = max(24, min(btn_h - 20, 40))
            self.setIconSize(QSize(icon_sz, icon_sz))

    # -------------------------------------------------------------------------
    # Hotkey
    # -------------------------------------------------------------------------

    def _pick_hotkey(self):
        from app.dialogs.hotkey_dialog import HotkeyPickerDialog
        from app.hotkey_manager import hotkey_manager

        existing = self._collect_existing_hotkeys()

        dlg = HotkeyPickerDialog(
            current_hotkey=self.hotkey,
            existing_hotkeys=existing,
            parent=self
        )
        if dlg.exec():
            new_hk = dlg.hotkey
            self._unregister_hotkey()
            self.hotkey = new_hk
            if new_hk:
                self._register_hotkey()
            self._refresh_tooltip()

    def _collect_existing_hotkeys(self):
        existing = []
        try:
            main_win = self.window()
            if hasattr(main_win, 'tabs'):
                for i in range(main_win.tabs.count()):
                    page = main_win.tabs.widget(i)
                    if hasattr(page, 'get_sound_buttons'):
                        for btn in page.get_sound_buttons():
                            if btn is not self and btn.hotkey:
                                existing.append(btn.hotkey)
        except Exception:
            pass
        return existing

    def _register_hotkey(self):
        if not self.hotkey:
            return
        from app.hotkey_manager import hotkey_manager
        hotkey_manager.register(self.hotkey, self.on_click)

    def _unregister_hotkey(self):
        if not self.hotkey:
            return
        from app.hotkey_manager import hotkey_manager
        hotkey_manager.unregister(self.hotkey)

    def _refresh_tooltip(self):
        fade_info = ""
        if self.fade_in_duration > 0 or self.fade_out_duration > 0:
            fade_info = f"  |  Fade in: {self.fade_in_duration}ms  |  Fade out: {self.fade_out_duration}ms"
        if self.hotkey:
            display = "  +  ".join(p.capitalize() for p in self.hotkey.split("+"))
            self.setToolTip(f"{self.sound_name}\nHotkey: {display}{fade_info}")
        else:
            self.setToolTip(self.sound_name + fade_info)

    # -------------------------------------------------------------------------
    # Search Highlight
    # -------------------------------------------------------------------------

    def set_search_highlight(self, active: bool):
        if self._search_highlighted == active:
            return
        self._search_highlighted = active
        if active:
            base = (
                f"background-color: rgb({self.color.red()},{self.color.green()},{self.color.blue()});"
                if self.color else ""
            )
            self.setStyleSheet(
                f"QPushButton#SoundButton {{ {base} border: 2px solid #FFD700; "
                f"background-color: {'rgb(' + str(self.color.red()) + ',' + str(self.color.green()) + ',' + str(self.color.blue()) + ')' if self.color else '#4A4200'}; }}"
            )
        else:
            self._apply_normal_style()

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
        self._refresh_tooltip()
        if self.icon_path:
            self._apply_icon()

    def _apply_color(self, color: QColor):
        r, g, b = color.red(), color.green(), color.blue()
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
