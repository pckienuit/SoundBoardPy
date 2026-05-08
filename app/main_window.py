from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTabWidget, QPushButton, QInputDialog, QMessageBox,
                             QMenu, QLabel)
from PyQt6.QtGui import QActionGroup, QShortcut, QKeySequence
from PyQt6.QtCore import Qt, QTimer
from app.tab_page import TabPage
from app.config_manager import ConfigManager
from app.widgets.snackbar import Snackbar
from app.widgets.search_panel import SearchPanel
from app.widgets.volume_meter import VolumeMeterWidget
from app.widgets.timeline_panel import TimelinePanel
import os


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sound Board")
        self.resize(736, 664)
        self.config_manager = ConfigManager("soundboard_config.json")
        self._undo_state = None
        self._search_results = []
        self._search_cursor = 0
        self._current_theme = "dark"
        self._passthrough_dlg = None
        self._global_crossfade_ms = 300

        self._init_ui()
        self._load_config()

        # Auto-save every 2 minutes
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(2 * 60 * 1000)
        self._autosave_timer.timeout.connect(self._save_config)
        self._autosave_timer.start()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────────────────────
        toolbar = QWidget()
        toolbar.setStyleSheet("background-color: #1E1E1E;")
        toolbar.setFixedHeight(42)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)
        toolbar_layout.setSpacing(4)
        toolbar_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        btn_style = """
            QPushButton {
                background: transparent; color: #CCCCCC;
                border: none; padding: 4px 10px; font-size: 12px;
            }
            QPushButton:hover { background: #333333; color: #FFFFFF; }
            QPushButton:pressed { background: #00AEEF; color: #FFFFFF; }
        """

        self.btn_silence = QPushButton("silence")
        self.btn_rename_page = QPushButton("rename page")
        self.btn_remove_page = QPushButton("remove page")
        self.btn_add_page = QPushButton("add page")
        self.btn_about = QPushButton("about")
        self.btn_search = QPushButton("🔍 search")
        self.btn_overflow = QPushButton("•••")

        for btn in [self.btn_silence, self.btn_rename_page, self.btn_remove_page,
                    self.btn_add_page, self.btn_about, self.btn_search, self.btn_overflow]:
            btn.setStyleSheet(btn_style)
            toolbar_layout.addWidget(btn)

        # Volume meter (right of toolbar)
        self.volume_meter = VolumeMeterWidget()
        toolbar_layout.addWidget(self.volume_meter)

        self.btn_silence.setToolTip("Stop all sounds (Esc)")
        self.btn_search.setToolTip("Search sounds (Ctrl+F)")
        self._build_overflow_menu()

        self.btn_silence.clicked.connect(self.silence_clicked)
        self.btn_add_page.clicked.connect(self.add_page_clicked)
        self.btn_rename_page.clicked.connect(self.rename_page_clicked)
        self.btn_remove_page.clicked.connect(self.remove_page_clicked)
        self.btn_about.clicked.connect(self._show_about)
        self.btn_search.clicked.connect(self._open_search)

        main_layout.addWidget(toolbar)

        # ── Search Panel ──────────────────────────────────────────────────────
        self.search_panel = SearchPanel()
        self.search_panel.search_changed.connect(self._on_search_changed)
        self.search_panel.closed.connect(self._on_search_closed)
        main_layout.addWidget(self.search_panel)

        # ── Tabs ─────────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._tab_context_menu)
        main_layout.addWidget(self.tabs)

        # ── Timeline Panel ────────────────────────────────────────────────────
        self.timeline_panel = TimelinePanel()
        self.timeline_panel.stream_stop_requested.connect(self._on_timeline_stop)
        self.timeline_panel.fade_all_requested.connect(self._fade_all)
        self.timeline_panel.stop_all_requested.connect(self._stop_all_immediately)
        self.timeline_panel.crossfade_changed.connect(self._on_crossfade_changed)
        self.timeline_panel.set_crossfade_ms(self._global_crossfade_ms)
        main_layout.addWidget(self.timeline_panel)

        # ── Snackbar ─────────────────────────────────────────────────────────
        self.snackbar = Snackbar(central_widget)
        self.snackbar.setFixedWidth(self.width())
        main_layout.addWidget(self.snackbar)

        # ── Shortcuts ─────────────────────────────────────────────────────────
        sc_search = QShortcut(QKeySequence("Ctrl+F"), self)
        sc_search.activated.connect(self._open_search)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "snackbar"):
            self.snackbar.setFixedWidth(self.width())

    def _build_overflow_menu(self):
        from app.audio_engine import audio_engine
        menu = QMenu(self)

        # ── Grid config ──────────────────────────────────────────────────────
        action_grid = menu.addAction("Change Button Grid…")
        action_grid.triggered.connect(self._change_grid)

        menu.addSeparator()

        # ── Import / Export ───────────────────────────────────────────────────
        action_import_export = menu.addAction("📦  Import / Export…")
        action_import_export.triggered.connect(self._open_import_export)

        # ── Audio Passthrough ─────────────────────────────────────────────────
        action_passthrough = menu.addAction("🎙  Audio Passthrough…")
        action_passthrough.triggered.connect(self._open_passthrough)

        menu.addSeparator()

        # ── Output device sub-menu ────────────────────────────────────────────
        self.device_menu = menu.addMenu("Sound Output Device")
        self.device_action_group = QActionGroup(self)
        self.device_action_group.setExclusive(True)

        devices = audio_engine.get_devices()
        for idx, dev in enumerate(devices):
            if dev['max_output_channels'] > 0:
                action = self.device_menu.addAction(dev['name'])
                action.setCheckable(True)
                action.setData(idx)
                self.device_action_group.addAction(action)
                if idx == 0:
                    action.setChecked(True)
                action.triggered.connect(self._on_device_selected)

        menu.addSeparator()

        # ── Timeline panel toggle ────────────────────────────────────────────
        self.action_timeline = menu.addAction("⏱  Timeline Panel")
        self.action_timeline.setCheckable(True)
        self.action_timeline.setChecked(True)
        self.action_timeline.triggered.connect(self._toggle_timeline_panel)

        menu.addSeparator()

        # ── Theme switcher ────────────────────────────────────────────────────
        self.action_light_mode = menu.addAction("☀  Light Mode")
        self.action_light_mode.setCheckable(True)
        self.action_light_mode.triggered.connect(self._toggle_theme)

        self.btn_overflow.setMenu(menu)

    # ── Timeline panel signal handlers ────────────────────────────────────────

    def _on_timeline_stop(self, stream_id: int):
        """Stop a specific stream from the timeline panel."""
        from app.audio_engine import audio_engine
        # Find the button owning this stream
        for i in range(self.tabs.count()):
            page = self.tabs.widget(i)
            for btn in page.get_sound_buttons():
                if btn.stream_id == stream_id:
                    btn._stop_sound(triggered_by="timeline")
                    return

    def _fade_all(self):
        """Fade out all playing sounds."""
        from app.audio_engine import audio_engine
        streams = audio_engine.get_playing_streams()
        for s in streams:
            audio_engine.fade_out(s["stream_id"])

    def _stop_all_immediately(self):
        """Hard-stop all sounds immediately."""
        from app.audio_engine import audio_engine
        audio_engine.stop_all()
        for i in range(self.tabs.count()):
            page = self.tabs.widget(i)
            for btn in page.get_sound_buttons():
                btn.is_playing = False
                btn.is_paused = False
                btn.stream_id = None
                btn._apply_normal_style()

    def _on_crossfade_changed(self, ms: int):
        self._global_crossfade_ms = ms

    def _toggle_timeline_panel(self, checked: bool):
        self.timeline_panel.setVisible(checked)

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        config_data = self.config_manager.load()
        if not config_data or "tabs" not in config_data:
            self._add_new_page("Page 1")
            return

        # Restore theme preference
        saved_theme = config_data.get("theme", "dark")
        if saved_theme != self._current_theme:
            self._apply_theme(saved_theme)

        # Restore global crossfade
        self._global_crossfade_ms = config_data.get("global_crossfade_ms", 300)
        self.timeline_panel.set_crossfade_ms(self._global_crossfade_ms)

        for tab_data in config_data["tabs"]:
            page = TabPage(rows=tab_data.get("rows", 5), cols=tab_data.get("cols", 2))
            self.tabs.addTab(page, tab_data.get("title", "Page"))
            buttons = page.get_sound_buttons()
            for idx, btn_data in enumerate(tab_data.get("buttons", [])):
                if idx < len(buttons) and btn_data.get("sound_path"):
                    btn = buttons[idx]
                    btn.set_sound(btn_data["sound_path"], btn_data.get("sound_name"))
                    btn.loop = btn_data.get("loop", False)
                    btn.volume_offset = btn_data.get("volume_offset", 0)
                    btn.stop_all_sounds = btn_data.get("stop_all_sounds", False)
                    color_str = btn_data.get("color")
                    if color_str:
                        from PyQt6.QtGui import QColor
                        c = QColor(color_str)
                        if c.isValid():
                            btn.color = c
                            btn._apply_color(c)
                    hk = btn_data.get("hotkey", "")
                    if hk:
                        btn.hotkey = hk
                        btn._register_hotkey()
                        btn._refresh_tooltip()
                    icon_p = btn_data.get("icon_path", "")
                    if icon_p and os.path.exists(icon_p):
                        btn.icon_path = icon_p
                        btn._apply_icon()
                    # Load fade settings
                    btn.fade_in_duration = btn_data.get("fade_in_duration", 0)
                    btn.fade_out_duration = btn_data.get("fade_out_duration", 0)
                    btn.fade_mode = btn_data.get("fade_mode", "auto")
                    btn.crossfade_duration = btn_data.get("crossfade_duration", 0)

    def _save_config(self):
        data = {
            "tabs": [],
            "theme": self._current_theme,
            "global_crossfade_ms": self._global_crossfade_ms,
        }
        for i in range(self.tabs.count()):
            page = self.tabs.widget(i)
            tab_data = {
                "title": self.tabs.tabText(i),
                "rows": page.rows,
                "cols": page.cols,
                "buttons": []
            }
            for btn in page.get_sound_buttons():
                tab_data["buttons"].append({
                    "sound_name": btn.sound_name,
                    "sound_path": btn.sound_path,
                    "loop": btn.loop,
                    "volume_offset": btn.volume_offset,
                    "stop_all_sounds": btn.stop_all_sounds,
                    "color": btn.color.name() if btn.color else None,
                    "hotkey": btn.hotkey,
                    "icon_path": btn.icon_path,
                    "fade_in_duration": btn.fade_in_duration,
                    "fade_out_duration": btn.fade_out_duration,
                    "fade_mode": btn.fade_mode,
                    "crossfade_duration": btn.crossfade_duration,
                })
            data["tabs"].append(tab_data)
        self.config_manager.save(data)

    def closeEvent(self, event):
        self._save_config()
        super().closeEvent(event)

    # ── Toolbar actions ───────────────────────────────────────────────────────

    def silence_clicked(self):
        from app.audio_engine import audio_engine
        streams = audio_engine.get_playing_streams()
        if streams:
            # Fade out all, then hard-stop after a delay
            for s in streams:
                audio_engine.fade_out(s["stream_id"])
            # Schedule a hard-stop check in 3 seconds
            QTimer.singleShot(3000, self._check_fade_complete)
        else:
            self._reset_all_buttons()

    def _check_fade_complete(self):
        """Hard-stop any streams that are still active after fade timeout."""
        from app.audio_engine import audio_engine
        streams = audio_engine.get_playing_streams()
        if streams:
            audio_engine.stop_all()
            self._reset_all_buttons()

    def _reset_all_buttons(self):
        """Reset all button states after all sounds stop."""
        for i in range(self.tabs.count()):
            page = self.tabs.widget(i)
            for btn in page.get_sound_buttons():
                btn.is_playing = False
                btn.is_paused = False
                btn.stream_id = None
                btn._apply_normal_style()

    def _add_new_page(self, title):
        page = TabPage(rows=5, cols=2)
        self.tabs.addTab(page, title)
        self.tabs.setCurrentWidget(page)

    def add_page_clicked(self):
        self._add_new_page("New Page")

    def rename_page_clicked(self):
        current_idx = self.tabs.currentIndex()
        if current_idx >= 0:
            current_title = self.tabs.tabText(current_idx)
            new_title, ok = QInputDialog.getText(
                self, "Rename Page", "New name:", text=current_title
            )
            if ok and new_title:
                self.tabs.setTabText(current_idx, new_title)

    def remove_page_clicked(self):
        current_idx = self.tabs.currentIndex()
        if current_idx < 0:
            return
        page = self.tabs.widget(current_idx)
        tab_name = self.tabs.tabText(current_idx)

        # Save undo state
        self._undo_state = self._capture_tab_state(current_idx)
        undo_tab_idx = current_idx

        # Stop all sounds on this tab
        for btn in page.get_sound_buttons():
            btn.stop()

        self.tabs.removeTab(current_idx)
        self.snackbar.show_message(
            f'Tab "{tab_name}" was removed.',
            undo_callback=lambda: self._restore_tab(self._undo_state, undo_tab_idx)
        )

    def _capture_tab_state(self, idx):
        page = self.tabs.widget(idx)
        buttons_data = []
        for btn in page.get_sound_buttons():
            buttons_data.append({
                "sound_name": btn.sound_name,
                "sound_path": btn.sound_path,
                "loop": btn.loop,
                "volume_offset": btn.volume_offset,
                "stop_all_sounds": btn.stop_all_sounds,
                "color": btn.color.name() if btn.color else None,
                "hotkey": btn.hotkey,
                "icon_path": btn.icon_path,
                "fade_in_duration": btn.fade_in_duration,
                "fade_out_duration": btn.fade_out_duration,
                "fade_mode": btn.fade_mode,
                "crossfade_duration": btn.crossfade_duration,
            })
        return {
            "title": self.tabs.tabText(idx),
            "rows": page.rows,
            "cols": page.cols,
            "buttons": buttons_data
        }

    def _restore_tab(self, state, insert_idx):
        page = TabPage(rows=state["rows"], cols=state["cols"])
        insert_at = min(insert_idx, self.tabs.count())
        self.tabs.insertTab(insert_at, page, state["title"])
        buttons = page.get_sound_buttons()
        for i, btn_data in enumerate(state["buttons"]):
            if i < len(buttons) and btn_data.get("sound_path"):
                btn = buttons[i]
                btn.set_sound(btn_data["sound_path"], btn_data.get("sound_name"))
                btn.loop = btn_data.get("loop", False)
                btn.volume_offset = btn_data.get("volume_offset", 0)
                btn.stop_all_sounds = btn_data.get("stop_all_sounds", False)
                color_str = btn_data.get("color")
                if color_str:
                    from PyQt6.QtGui import QColor
                    c = QColor(color_str)
                    if c.isValid():
                        btn.color = c
                        btn._apply_color(c)
                hk = btn_data.get("hotkey", "")
                if hk:
                    btn.hotkey = hk
                    btn._register_hotkey()
                    btn._refresh_tooltip()
                icon_p = btn_data.get("icon_path", "")
                if icon_p and os.path.exists(icon_p):
                    btn.icon_path = icon_p
                    btn._apply_icon()
                btn.fade_in_duration = btn_data.get("fade_in_duration", 0)
                btn.fade_out_duration = btn_data.get("fade_out_duration", 0)
                btn.fade_mode = btn_data.get("fade_mode", "auto")
                btn.crossfade_duration = btn_data.get("crossfade_duration", 0)
        self.tabs.setCurrentIndex(insert_at)

    def _change_grid(self):
        current_idx = self.tabs.currentIndex()
        if current_idx < 0:
            return
        page = self.tabs.widget(current_idx)
        from app.dialogs.grid_dialog import GridDialog
        dlg = GridDialog(page.rows, page.cols, parent=self)
        if dlg.exec():
            for btn in page.get_sound_buttons():
                btn.stop()
            page.set_grid(dlg.rows, dlg.cols)

    def _tab_context_menu(self, pos):
        idx = self.tabs.tabBar().tabAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        action_rename = menu.addAction("Rename")
        action_remove = menu.addAction("Remove")
        action_grid = menu.addAction("Change Button Grid…")
        action = menu.exec(self.tabs.tabBar().mapToGlobal(pos))
        if action == action_rename:
            self.tabs.setCurrentIndex(idx)
            self.rename_page_clicked()
        elif action == action_remove:
            self.tabs.setCurrentIndex(idx)
            self.remove_page_clicked()
        elif action == action_grid:
            self.tabs.setCurrentIndex(idx)
            self._change_grid()

    def _on_device_selected(self):
        action = self.sender()
        if action:
            from app.audio_engine import audio_engine
            audio_engine.set_output_device(action.data())

    # ── Import / Export ───────────────────────────────────────────────────────

    def _open_import_export(self):
        from app.dialogs.import_export_dialog import ImportExportDialog
        dlg = ImportExportDialog(
            get_config_fn=self._collect_config_dict,
            apply_config_fn=self._apply_imported_config,
            parent=self
        )
        dlg.exec()

    def _collect_config_dict(self) -> dict:
        """Build the same dict _save_config uses, without writing to disk."""
        data = {
            "tabs": [],
            "theme": self._current_theme,
            "global_crossfade_ms": self._global_crossfade_ms,
        }
        for i in range(self.tabs.count()):
            page = self.tabs.widget(i)
            tab_data = {
                "title": self.tabs.tabText(i),
                "rows": page.rows,
                "cols": page.cols,
                "buttons": [],
            }
            for btn in page.get_sound_buttons():
                tab_data["buttons"].append({
                    "sound_name": btn.sound_name,
                    "sound_path": btn.sound_path,
                    "loop": btn.loop,
                    "volume_offset": btn.volume_offset,
                    "stop_all_sounds": btn.stop_all_sounds,
                    "color": btn.color.name() if btn.color else None,
                    "hotkey": btn.hotkey,
                    "icon_path": btn.icon_path,
                    "fade_in_duration": btn.fade_in_duration,
                    "fade_out_duration": btn.fade_out_duration,
                    "fade_mode": btn.fade_mode,
                    "crossfade_duration": btn.crossfade_duration,
                })
            data["tabs"].append(tab_data)
        return data

    def _apply_imported_config(self, config: dict):
        """Replace current board with imported config (same logic as _load_config)."""
        self.silence_clicked()
        while self.tabs.count() > 0:
            self.tabs.removeTab(0)
        for tab_data in config.get("tabs", []):
            page = TabPage(rows=tab_data.get("rows", 5), cols=tab_data.get("cols", 2))
            self.tabs.addTab(page, tab_data.get("title", "Page"))
            buttons = page.get_sound_buttons()
            for idx, btn_data in enumerate(tab_data.get("buttons", [])):
                if idx < len(buttons) and btn_data.get("sound_path"):
                    btn = buttons[idx]
                    btn.set_sound(btn_data["sound_path"], btn_data.get("sound_name"))
                    btn.loop = btn_data.get("loop", False)
                    btn.volume_offset = btn_data.get("volume_offset", 0)
                    btn.stop_all_sounds = btn_data.get("stop_all_sounds", False)
                    color_str = btn_data.get("color")
                    if color_str:
                        from PyQt6.QtGui import QColor
                        c = QColor(color_str)
                        if c.isValid():
                            btn.color = c
                            btn._apply_color(c)
                    hk = btn_data.get("hotkey", "")
                    if hk:
                        btn.hotkey = hk
                        btn._register_hotkey()
                        btn._refresh_tooltip()
                    icon_p = btn_data.get("icon_path", "")
                    if icon_p and os.path.exists(icon_p):
                        btn.icon_path = icon_p
                        btn._apply_icon()
                    btn.fade_in_duration = btn_data.get("fade_in_duration", 0)
                    btn.fade_out_duration = btn_data.get("fade_out_duration", 0)
                    btn.fade_mode = btn_data.get("fade_mode", "auto")
                    btn.crossfade_duration = btn_data.get("crossfade_duration", 0)
        self._global_crossfade_ms = config.get("global_crossfade_ms", 300)
        self.timeline_panel.set_crossfade_ms(self._global_crossfade_ms)
        self._save_config()

    # ── Passthrough ───────────────────────────────────────────────────────────

    def _open_passthrough(self):
        from app.dialogs.passthrough_dialog import PassthroughDialog
        if self._passthrough_dlg is None or not self._passthrough_dlg.isVisible():
            self._passthrough_dlg = PassthroughDialog(parent=self)
            self._passthrough_dlg.show()
        else:
            self._passthrough_dlg.raise_()
            self._passthrough_dlg.activateWindow()

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _toggle_theme(self, checked: bool):
        self._apply_theme("light" if checked else "dark")

    def _apply_theme(self, theme: str):
        self._current_theme = theme
        theme_file = os.path.join(
            os.path.dirname(__file__), "styles",
            "light_theme.qss" if theme == "light" else "dark_theme.qss"
        )
        try:
            with open(theme_file, "r", encoding="utf-8") as f:
                self.parent().setStyleSheet(f.read()) if self.parent() else \
                    self.setStyleSheet(f.read())
            from PyQt6.QtWidgets import QApplication
            QApplication.instance().setStyleSheet(
                open(theme_file, "r", encoding="utf-8").read()
            )
        except Exception as e:
            print(f"Theme load error: {e}")
        if hasattr(self, "action_light_mode"):
            self.action_light_mode.setChecked(theme == "light")

    def _show_about(self):
        QMessageBox.about(
            self, "About Sound Board",
            "Sound Board v1.0\n\nA Python clone of the SoundBoard C# app.\n"
            "Built with PyQt6 + sounddevice."
        )

    # ── Search ───────────────────────────────────────────────────────────────

    def _open_search(self):
        self.search_panel.open_panel()

    def _on_search_closed(self):
        self._clear_all_highlights()
        self._search_results = []
        self._search_cursor = 0

    def _on_search_changed(self, query: str):
        # Navigation signals from prev/next buttons
        if query.startswith("__nav_next__"):
            real_query = query[len("__nav_next__"):]
            if self._search_results:
                self._search_cursor = (self._search_cursor + 1) % len(self._search_results)
                self._jump_to_cursor()
            return
        if query.startswith("__nav_prev__"):
            real_query = query[len("__nav_prev__"):]
            if self._search_results:
                self._search_cursor = (self._search_cursor - 1) % len(self._search_results)
                self._jump_to_cursor()
            return

        self._clear_all_highlights()
        self._search_results = []
        self._search_cursor = 0

        if not query:
            self.search_panel.clear_result_info()
            return

        q = query.lower()
        for tab_idx in range(self.tabs.count()):
            page = self.tabs.widget(tab_idx)
            for btn in page.get_sound_buttons():
                if btn.sound_name and q in btn.sound_name.lower():
                    self._search_results.append((tab_idx, btn))

        for _, btn in self._search_results:
            btn.set_search_highlight(True)

        total = len(self._search_results)
        self.search_panel.set_result_info(total, self._search_cursor + 1 if total else 0)

        if self._search_results:
            self._jump_to_cursor()

    def _jump_to_cursor(self):
        if not self._search_results:
            return
        tab_idx, btn = self._search_results[self._search_cursor]
        self.tabs.setCurrentIndex(tab_idx)
        btn.setFocus()
        total = len(self._search_results)
        self.search_panel.set_result_info(total, self._search_cursor + 1)

    def _clear_all_highlights(self):
        for i in range(self.tabs.count()):
            page = self.tabs.widget(i)
            for btn in page.get_sound_buttons():
                btn.set_search_highlight(False)

    # ── Key Events ───────────────────────────────────────────────────────────

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            if self.search_panel.isVisible():
                self.search_panel.close_panel()
            else:
                self.silence_clicked()
        super().keyPressEvent(event)
