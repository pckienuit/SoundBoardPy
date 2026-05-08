from PyQt6.QtWidgets import (QPushButton, QMenu, QFileDialog, QInputDialog,
                             QColorDialog, QDialog, QVBoxLayout, QHBoxLayout,
                             QLabel, QSlider, QDialogButtonBox)
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
        self.icon_path = ""        # optional image path
        self.color = None          # QColor or None
        self.volume_offset = 0
        self.loop = False
        self.stop_all_sounds = False
        self.next_sound = ""
        self.hotkey = ""           # e.g. "ctrl+alt+a"

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
        self.setToolButtonStyle if False else None  # no-op
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

        # Collect all hotkeys already registered (excluding self)
        existing = self._collect_existing_hotkeys()

        dlg = HotkeyPickerDialog(
            current_hotkey=self.hotkey,
            existing_hotkeys=existing,
            parent=self
        )
        if dlg.exec():
            new_hk = dlg.hotkey
            # Unregister old hotkey first
            self._unregister_hotkey()
            self.hotkey = new_hk
            if new_hk:
                self._register_hotkey()
            self._refresh_tooltip()

    def _collect_existing_hotkeys(self):
        """Scan all SoundButtons in all tabs for registered hotkeys."""
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
        if self.hotkey:
            display = "  +  ".join(p.capitalize() for p in self.hotkey.split("+"))
            self.setToolTip(f"{self.sound_name}\nHotkey: {display}")
        else:
            self.setToolTip(self.sound_name)

    # -------------------------------------------------------------------------
    # Search Highlight
    # -------------------------------------------------------------------------

    def set_search_highlight(self, active: bool):
        """Highlight or un-highlight this button for search results."""
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
