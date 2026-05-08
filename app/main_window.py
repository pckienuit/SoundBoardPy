from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTabWidget, QPushButton, QInputDialog, QMessageBox,
                             QMenu)
from PyQt6.QtGui import QActionGroup
from PyQt6.QtCore import Qt, QTimer
from app.tab_page import TabPage
from app.config_manager import ConfigManager
from app.widgets.snackbar import Snackbar


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sound Board")
        self.resize(736, 664)
        self.config_manager = ConfigManager("soundboard_config.json")
        self._undo_state = None

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
        self.btn_overflow = QPushButton("•••")

        for btn in [self.btn_silence, self.btn_rename_page, self.btn_remove_page,
                    self.btn_add_page, self.btn_about, self.btn_overflow]:
            btn.setStyleSheet(btn_style)
            toolbar_layout.addWidget(btn)

        self.btn_silence.setToolTip("Stop all sounds (Esc)")
        self._build_overflow_menu()

        self.btn_silence.clicked.connect(self.silence_clicked)
        self.btn_add_page.clicked.connect(self.add_page_clicked)
        self.btn_rename_page.clicked.connect(self.rename_page_clicked)
        self.btn_remove_page.clicked.connect(self.remove_page_clicked)
        self.btn_about.clicked.connect(self._show_about)

        main_layout.addWidget(toolbar)

        # ── Tabs ─────────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.tabBar().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabs.tabBar().customContextMenuRequested.connect(self._tab_context_menu)
        main_layout.addWidget(self.tabs)

        # ── Snackbar ─────────────────────────────────────────────────────────
        self.snackbar = Snackbar(central_widget)
        self.snackbar.setFixedWidth(self.width())
        main_layout.addWidget(self.snackbar)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "snackbar"):
            self.snackbar.setFixedWidth(self.width())

    def _build_overflow_menu(self):
        from app.audio_engine import audio_engine
        menu = QMenu(self)

        # ── Grid config for current tab ───────────────────────────────────────
        action_grid = menu.addAction("Change Button Grid…")
        action_grid.triggered.connect(self._change_grid)

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

        self.btn_overflow.setMenu(menu)

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        config_data = self.config_manager.load()
        if not config_data or "tabs" not in config_data:
            self._add_new_page("Page 1")
            return

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

    def _save_config(self):
        data = {"tabs": []}
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
                })
            data["tabs"].append(tab_data)
        self.config_manager.save(data)

    def closeEvent(self, event):
        self._save_config()
        super().closeEvent(event)

    # ── Toolbar actions ───────────────────────────────────────────────────────

    def silence_clicked(self):
        from app.audio_engine import audio_engine
        audio_engine.stop_all()
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

    def _show_about(self):
        QMessageBox.about(
            self, "About Sound Board",
            "Sound Board v1.0\n\nA Python clone of the SoundBoard C# app.\n"
            "Built with PyQt6 + sounddevice."
        )

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.silence_clicked()
        super().keyPressEvent(event)
