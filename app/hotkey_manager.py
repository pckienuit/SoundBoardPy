import keyboard
import threading

class HotkeyManager:
    def __init__(self):
        self.hotkeys = {} # key_combination -> callback
        self.lock = threading.Lock()

    def register(self, combination, callback):
        """
        Registers a global hotkey combination.
        combination: str (e.g. "ctrl+alt+a")
        callback: function to call
        """
        with self.lock:
            if combination in self.hotkeys:
                self.unregister(combination)
            
            try:
                # keyboard module needs to hook into OS events
                keyboard.add_hotkey(combination, callback, suppress=True)
                self.hotkeys[combination] = callback
                return True
            except Exception as e:
                print(f"Error registering hotkey {combination}: {e}")
                return False

    def unregister(self, combination):
        """
        Unregisters a specific combination
        """
        with self.lock:
            if combination in self.hotkeys:
                try:
                    keyboard.remove_hotkey(combination)
                except Exception:
                    pass
                del self.hotkeys[combination]

    def clear_all(self):
        with self.lock:
            keyboard.unhook_all_hotkeys()
            self.hotkeys.clear()

hotkey_manager = HotkeyManager()
