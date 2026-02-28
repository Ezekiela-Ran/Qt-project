"""
    This is the main entry point of the application
"""
import sys
from PySide6 import QtWidgets
from views.foundations.windows import BaseWindow
from views.layouts.list_layout import ListLayout
from views.layouts.menu_layout import MenuLayout

class Window(BaseWindow):
    
    """
        This is the main window of the application.
        It sets up the window title and its geometry to match the screen size.
    """
    def __init__(self):
        super().__init__()
        self._setup_views()

        
    def _setup_views(self): 
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0) 
        list_widget = ListLayout(self) 
        layout.addWidget(list_widget) 
        self.setLayout(layout)
    

        
      

if __name__ == "__main__":
    
    app = QtWidgets.QApplication([])

    win = Window()
    win.show()

    sys.exit(app.exec())