from PySide6 import QtGui, QtWidgets

from utils.path_utils import resolve_resource_path

class Window(QtWidgets.QWidget):
    
    """
        Voici la fenêtre principale et ses configurations
    """
    def __init__(self):
        super().__init__()
        
        height = self.screen().size().height()
        width = self.screen().size().width()
        
        self.setWindowTitle("FaC (Facture et Certificat)")
        icon_path = resolve_resource_path("images/image.png")
        if icon_path.exists():
            self.setWindowIcon(QtGui.QIcon(str(icon_path)))
        self.setGeometry(0, 0, width, height)
        self.window_layout = QtWidgets.QVBoxLayout(self)
        self.window_layout.setContentsMargins(0, 0, 0, 0)