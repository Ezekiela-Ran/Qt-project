from PySide6 import QtWidgets
from views.components.menu import MenuComponent

class MenuLayout(QtWidgets.QWidget):
    """
    Widget qui contient la barre de menus dans un layout vertical.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_layout()

    def _setup_layout(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        menu = MenuComponent(self)   # ta barre de menus
        layout.setMenuBar(menu)      # on place la barre de menus dans le layout
        self.setLayout(layout)
