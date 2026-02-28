from PySide6 import QtWidgets


class MenuBar(QtWidgets.QMenuBar):
    def __init__(self, parent):
        super().__init__(parent)
        
        # Menu pour les fichiers
        self.file_menu = self.addMenu("Fichier")
        self.new_file_menu = QtWidgets.QMenu("Nouveau")
        self.file_menu.addMenu(self.new_file_menu)
        self.new_file_menu.addAction("Facture")
        self.new_file_menu.addAction("Facture proforma")
        
        # Menu pour les thèmes
        self.theme_menu = self.addMenu("Thème")
        self.theme_menu.addAction("Clair")
        self.theme_menu.addAction("Sombre")
        
        