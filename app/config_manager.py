import json
import os
import shutil
from datetime import datetime

class ConfigManager:
    def __init__(self, config_path="config.json"):
        self.config_path = config_path

    def load(self):
        if not os.path.exists(self.config_path):
            return None
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            return None

    def save(self, data):
        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(self.config_path)), exist_ok=True)
        
        # Backup existing
        if os.path.exists(self.config_path):
            backup_path = f"{self.config_path}-{datetime.now().strftime('%Y%m%d%H%M%S')}.bak"
            shutil.copy(self.config_path, backup_path)
            self._cleanup_backups()
            
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def _cleanup_backups(self):
        directory = os.path.dirname(os.path.abspath(self.config_path))
        base_name = os.path.basename(self.config_path)
        backups = []
        for file in os.listdir(directory):
            if file.startswith(base_name) and file.endswith(".bak"):
                backups.append(os.path.join(directory, file))
        
        # Sort by modification time, newest first
        backups.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        # Keep only the newest 5
        MAX_BACKUPS = 5
        if len(backups) > MAX_BACKUPS:
            for file in backups[MAX_BACKUPS:]:
                try:
                    os.remove(file)
                except Exception:
                    pass
