import sys
sys.path.insert(0, ".")

try:
    import app
    print("OK: app")
    from app import config_manager
    print("OK: config_manager")
    from app import audio_engine
    print("OK: audio_engine")
    from app import hotkey_manager
    print("OK: hotkey_manager")
    from app import tab_page
    print("OK: tab_page")
    from app import sound_button
    print("OK: sound_button")
    from app import main_window
    print("OK: main_window")
    print("\nAll imports successful!")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
