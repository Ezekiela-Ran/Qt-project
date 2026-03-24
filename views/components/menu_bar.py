from PySide6 import QtWidgets

class MenuBar(QtWidgets.QMenuBar):
    def __init__(self, parent):
        super().__init__(parent)       
        self.parent = parent
        
        # Menu pour les fichiers
        self.file_menu = self.addMenu("Fichier")
        self.new_file_menu = QtWidgets.QMenu("Nouveau")
        self.file_menu.addMenu(self.new_file_menu)

        # Actions individuelles
        facture_action = self.new_file_menu.addAction("Facture")
        facture_action.triggered.connect(lambda: self.parent.menubar_click_standard())

        proforma_action = self.new_file_menu.addAction("Facture proforma")
        proforma_action.triggered.connect(lambda: self.parent.menubar_click_proforma())

        init_counters_action = self.file_menu.addAction("Initialiser facture et Ref.b.analyse")
        init_counters_action.triggered.connect(lambda: self.parent.menubar_click_initialize_counters())
        
        # Action de réinitialisation : archive les données de l'année précédente et remet les compteurs à 1
        reset_action = self.file_menu.addAction("Réinitialisation")
        reset_action.triggered.connect(lambda: self.parent.menubar_click_reset())
        self._apply_styles()
    
    def _apply_styles(self): 
        with open("styles/menu.qss", "r") as f:
            self.setStyleSheet(f.read())
