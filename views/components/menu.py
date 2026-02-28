from PySide6 import QtWidgets

class MenuComponent(QtWidgets.QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_menu()
        self._apply_styles()

    def _setup_menu(self):
        file_menu = self.addMenu("Fichier")
        file_menu.addAction("Nouveau")
        file_menu.addAction("Quitter")

        help_menu = self.addMenu("Aide")
        help_menu.addAction("À propos")
        
    
    def _apply_styles(self):
        with open("styles/menu.qss", "r") as f: 
            self.setStyleSheet(f.read())
