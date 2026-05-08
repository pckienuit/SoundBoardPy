import sys
import os
from PyQt6.QtWidgets import QApplication
from app.main_window import MainWindow

def load_stylesheet(app):
    style_path = os.path.join(os.path.dirname(__file__), "app", "styles", "dark_theme.qss")
    if os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

def main():
    app = QApplication(sys.argv)
    
    # Set application details
    app.setApplicationName("Sound Board")
    app.setApplicationVersion("1.0.0")
    
    # Load stylesheet
    load_stylesheet(app)
    
    # Show main window
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
