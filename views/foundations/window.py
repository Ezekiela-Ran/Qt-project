from PySide6 import QtWidgets


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