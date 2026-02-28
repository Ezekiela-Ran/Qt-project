from PySide6 import QtWidgets


class MenuBar(QtWidgets.QMenuBar):
    def __init__(self, parent):
        super().__init__(parent)
        
        self._initialise_file_menu()
        self._initialise_theme_menu()
        
    def _initialise_file_menu(self):
        
        # Menu pour les fichiers
        file_menu = self.addMenu("Fichier")
        
        # Sous-menu pour les nouveaux fichiers
        new_file_sub_menu = QtWidgets.QMenu("Nouveau")
        file_menu.addMenu(new_file_sub_menu)
        
        # Actions pour les nouveaux fichiers
        new_file_sub_menu.addAction("Facture")
        new_file_sub_menu.addAction("Facture proforma")
        
    def _initialise_theme_menu(self):
        
        # Menu pour les thèmes
        theme_menu = self.addMenu("Thème")
        
        # Actions pour les thèmes
        theme_menu.addAction("Clair")
        theme_menu.addAction("Sombre")
        