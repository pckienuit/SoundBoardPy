from PyQt6.QtWidgets import QWidget, QGridLayout
from app.sound_button import SoundButton

class TabPage(QWidget):
    def __init__(self, rows=5, cols=2):
        super().__init__()
        self.rows = rows
        self.cols = cols
        
        self.grid_layout = QGridLayout(self)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        self.grid_layout.setSpacing(10)
        
        self._init_grid()

    def _init_grid(self):
        # Clear existing layout if any
        for i in reversed(range(self.grid_layout.count())): 
            widget_to_remove = self.grid_layout.itemAt(i).widget()
            if widget_to_remove is not None:
                widget_to_remove.setParent(None)
                
        # Populate buttons
        for r in range(self.rows):
            for c in range(self.cols):
                button = SoundButton(self)
                self.grid_layout.addWidget(button, r, c)

    def set_grid(self, rows, cols):
        self.rows = rows
        self.cols = cols
        self._init_grid()

    def get_sound_buttons(self):
        buttons = []
        for i in range(self.grid_layout.count()):
            widget = self.grid_layout.itemAt(i).widget()
            if isinstance(widget, SoundButton):
                buttons.append(widget)
        return buttons
