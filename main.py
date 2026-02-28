"""
    This is the main entry point of the application
"""
import sys
from PySide6 import QtWidgets
from views.components.menu_bar import MenuBar

class Window(QtWidgets.QWidget):
    
    """
        This is the main window of the application.
        It sets up the window title and its geometry to match the screen size.
    """
    def __init__(self):
        super().__init__()
        
        height = self.screen().size().height()
        width = self.screen().size().width()
        
        self.setWindowTitle("Acssqda")
        self.setGeometry(0, 0, width, height)
        
        
if __name__ == "__main__":
    
    app = QtWidgets.QApplication([])

    win = Window()
    MenuBar(win)
    win.show()
    
    sys.exit(app.exec())