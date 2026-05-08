"""Import/Export dialog — ZIP bundle (config + audio files) or JSON only."""
import os
import json
import shutil
import zipfile
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QProgressBar, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont


class _ExportWorker(QThread):
    progress = pyqtSignal(int)
    done = pyqtSignal(str)  # path or error message
    error = pyqtSignal(str)

    def __init__(self, config_data: dict, zip_path: str):
        super().__init__()
        self.config_data = config_data
        self.zip_path = zip_path

    def run(self):
        try:
            # Collect all unique audio files
            audio_files = []
            for tab in self.config_data.get("tabs", []):
                for btn in tab.get("buttons", []):
                    p = btn.get("sound_path", "")
                    icon_p = btn.get("icon_path", "")
                    if p and os.path.exists(p) and p not in audio_files:
                        audio_files.append(p)
                    if icon_p and os.path.exists(icon_p) and icon_p not in audio_files:
                        audio_files.append(icon_p)

            total = len(audio_files) + 1  # +1 for JSON
            done_count = 0

            # Remap config paths → relative "sounds/<filename>"
            import copy
            export_config = copy.deepcopy(self.config_data)
            for tab in export_config.get("tabs", []):
                for btn in tab.get("buttons", []):
                    if btn.get("sound_path"):
                        btn["sound_path"] = "sounds/" + os.path.basename(btn["sound_path"])
                    if btn.get("icon_path"):
                        btn["icon_path"] = "icons/" + os.path.basename(btn["icon_path"])

            with zipfile.ZipFile(self.zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                # Write config
                zf.writestr("soundboard_config.json", json.dumps(export_config, indent=4))
                done_count += 1
                self.progress.emit(int(done_count / total * 100))

                # Write audio files
                for path in audio_files:
                    folder = "sounds" if any(
                        path.lower().endswith(e) for e in
                        [".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma"]
                    ) else "icons"
                    arcname = f"{folder}/{os.path.basename(path)}"
                    zf.write(path, arcname)
                    done_count += 1
                    self.progress.emit(int(done_count / total * 100))

            self.done.emit(self.zip_path)
        except Exception as e:
            self.error.emit(str(e))


class _ImportWorker(QThread):
    progress = pyqtSignal(int)
    done = pyqtSignal(dict)   # restored config dict with absolute paths
    error = pyqtSignal(str)

    def __init__(self, zip_path: str, extract_dir: str):
        super().__init__()
        self.zip_path = zip_path
        self.extract_dir = extract_dir

    def run(self):
        try:
            os.makedirs(self.extract_dir, exist_ok=True)

            with zipfile.ZipFile(self.zip_path, "r") as zf:
                names = zf.namelist()
                total = len(names)
                for i, name in enumerate(names, 1):
                    zf.extract(name, self.extract_dir)
                    self.progress.emit(int(i / total * 100))

            # Load and remap config
            config_file = os.path.join(self.extract_dir, "soundboard_config.json")
            with open(config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            for tab in config.get("tabs", []):
                for btn in tab.get("buttons", []):
                    if btn.get("sound_path"):
                        btn["sound_path"] = os.path.join(
                            self.extract_dir, btn["sound_path"]
                        ).replace("/", os.sep)
                    if btn.get("icon_path"):
                        btn["icon_path"] = os.path.join(
                            self.extract_dir, btn["icon_path"]
                        ).replace("/", os.sep)

            self.done.emit(config)
        except Exception as e:
            self.error.emit(str(e))


class ImportExportDialog(QDialog):
    """Dialog for exporting/importing a soundboard ZIP bundle."""

    imported_config = pyqtSignal(dict)  # emitted after successful import

    def __init__(self, get_config_fn, apply_config_fn, parent=None):
        super().__init__(parent)
        self.get_config_fn = get_config_fn
        self.apply_config_fn = apply_config_fn
        self._worker = None

        self.setWindowTitle("Import / Export Soundboard")
        self.setFixedSize(420, 280)
        self.setModal(True)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Title
        title = QLabel("📦  Import / Export")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        layout.addWidget(title)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #444;")
        layout.addWidget(line)

        # Description
        desc = QLabel(
            "Export saves your entire soundboard — all tabs, buttons,\n"
            "audio files, and icons — into a single <b>.sbpack</b> ZIP file.\n"
            "Import loads a previously exported bundle."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        layout.addWidget(desc)

        # Progress bar (hidden initially)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setStyleSheet(
            "QProgressBar { border: none; background: #333; border-radius: 4px; }"
            "QProgressBar::chunk { background: #00AEEF; border-radius: 4px; }"
        )
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #00AEEF; font-size: 11px;")
        self.status_label.hide()
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self.btn_export = QPushButton("⬆  Export  (.sbpack)")
        self.btn_import = QPushButton("⬇  Import  (.sbpack)")
        self.btn_close = QPushButton("Close")

        for btn in [self.btn_export, self.btn_import]:
            btn.setMinimumHeight(36)
            btn.setStyleSheet(
                "QPushButton { background: #00AEEF; color: #000; border: none; "
                "border-radius: 3px; font-weight: bold; padding: 0 16px; }"
                "QPushButton:hover { background: #33C4FF; }"
                "QPushButton:pressed { background: #007AAF; }"
                "QPushButton:disabled { background: #333; color: #666; }"
            )
        self.btn_close.setMinimumHeight(36)
        self.btn_close.setStyleSheet(
            "QPushButton { background: #3B3B3B; color: #CCC; border: none; "
            "border-radius: 3px; padding: 0 16px; }"
            "QPushButton:hover { background: #555; }"
        )

        self.btn_export.clicked.connect(self._do_export)
        self.btn_import.clicked.connect(self._do_import)
        self.btn_close.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_export)
        btn_row.addWidget(self.btn_import)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------

    def _set_busy(self, busy: bool, msg: str = ""):
        self.btn_export.setEnabled(not busy)
        self.btn_import.setEnabled(not busy)
        if busy:
            self.progress_bar.setValue(0)
            self.progress_bar.show()
            self.status_label.setText(msg)
            self.status_label.show()
        else:
            self.progress_bar.hide()
            self.status_label.hide()

    def _do_export(self):
        zip_path, _ = QFileDialog.getSaveFileName(
            self, "Export Soundboard", "soundboard.sbpack",
            "SoundBoard Pack (*.sbpack);;ZIP Files (*.zip)"
        )
        if not zip_path:
            return

        config = self.get_config_fn()
        self._set_busy(True, "Exporting…")

        self._worker = _ExportWorker(config, zip_path)
        self._worker.progress.connect(self.progress_bar.setValue)
        self._worker.done.connect(self._on_export_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_export_done(self, path):
        self._set_busy(False)
        QMessageBox.information(self, "Export Complete",
                                f"Soundboard exported successfully:\n{path}")

    def _do_import(self):
        zip_path, _ = QFileDialog.getOpenFileName(
            self, "Import Soundboard", "",
            "SoundBoard Pack (*.sbpack *.zip)"
        )
        if not zip_path:
            return

        # Extract next to the zip file or app dir
        base_dir = os.path.dirname(zip_path)
        pack_name = os.path.splitext(os.path.basename(zip_path))[0]
        extract_dir = os.path.join(base_dir, f"imported_{pack_name}")

        self._set_busy(True, "Importing…")

        self._worker = _ImportWorker(zip_path, extract_dir)
        self._worker.progress.connect(self.progress_bar.setValue)
        self._worker.done.connect(self._on_import_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_import_done(self, config: dict):
        self._set_busy(False)
        reply = QMessageBox.question(
            self, "Import Complete",
            "Soundboard imported. Replace current board with imported one?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.apply_config_fn(config)
        self.accept()

    def _on_error(self, msg: str):
        self._set_busy(False)
        QMessageBox.critical(self, "Error", f"Operation failed:\n{msg}")
