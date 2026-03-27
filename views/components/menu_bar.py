from PySide6 import QtWidgets
from utils.path_utils import resolve_resource_path
from views.foundation.globals import GlobalVariable

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

        if GlobalVariable.is_admin():
            init_counters_action = self.file_menu.addAction("Initialiser facture et Ref.b.analyse")
            init_counters_action.triggered.connect(lambda: self.parent.menubar_click_initialize_counters())

            reset_action = self.file_menu.addAction("Réinitialisation")
            reset_action.triggered.connect(lambda: self.parent.menubar_click_reset())

            self.admin_menu = self.addMenu("Administration")
            users_action = self.admin_menu.addAction("Utilisateurs")
            users_action.triggered.connect(lambda: self.parent.menubar_click_manage_users())
        self._apply_styles()
    
    def _apply_styles(self): 
        with open(resolve_resource_path("styles/menu.qss"), "r", encoding="utf-8") as f:
            self.setStyleSheet(f.read())
