from PySide6 import QtWidgets
from views.layouts.menu_layout import MenuLayout

class ListLayout(QtWidgets.QWidget):
    """
    Widget principal qui contient MenuLayout et éventuellement d'autres widgets.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup()

    def _setup(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0) 
        menu_layout = MenuLayout(self)   # ton widget avec la barre de menus
        layout.addWidget(menu_layout)    # on ajoute MenuLayout dans ListLayout
        self.setLayout(layout)
