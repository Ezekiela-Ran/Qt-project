from PySide6 import QtWidgets

class BaseWindow(QtWidgets.QWidget):

    def __init__(self):
        super().__init__()
        self._setup_window("ACSQDA")
        
    def _setup_window(self, title):
        height = self.screen().size().height()
        width = self.screen().size().width()
        self.setWindowTitle(title)
        self.setGeometry(0, 0, width, height)
    
    
