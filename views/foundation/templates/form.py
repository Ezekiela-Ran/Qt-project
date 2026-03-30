from PySide6.QtWidgets import (
    QWidget, QLabel, QLineEdit, QFormLayout, QHBoxLayout, QSizePolicy
)
from utils.path_utils import resolve_resource_path

class FormTemplate(QWidget):
    def __init__(self):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        # Labels et inputs
        self.company_name_label = QLabel("Raison sociale:")
        self.company_name_input = QLineEdit()
        self.company_name_input.setObjectName("invoiceInput")

        self.responsable_label = QLabel("Responsable:")
        self.responsable_input = QLineEdit()
        self.responsable_input.setObjectName("invoiceInput")
        self.responsable_input.setReadOnly(True)

        self.stat_label = QLabel("Statistique :")
        self.stat_input = QLineEdit()
        self.stat_input.setObjectName("invoiceInput")

        self.nif_label = QLabel("NIF:")
        self.nif_input = QLineEdit()
        self.nif_input.setObjectName("invoiceInput")

        self.address_label = QLabel("Adresse:")
        self.address_input = QLineEdit()
        self.address_input.setObjectName("invoiceInput")

        # Layout principal horizontal (2 colonnes)
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(18)

        # Colonne gauche
        self.left_form = QFormLayout()
        self.left_form.setSpacing(6)
        self.left_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.left_form.addRow(self.company_name_label, self.company_name_input)
        self.left_form.addRow(self.stat_label, self.stat_input)
        self.left_form.addRow(self.address_label, self.address_input)

        # Colonne droite
        self.right_form = QFormLayout()
        self.right_form.setSpacing(6)
        self.right_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.right_form.addRow(self.responsable_label, self.responsable_input)
        self.right_form.addRow(self.nif_label, self.nif_input)

        # Ajouter les deux colonnes côte à côte
        main_layout.addLayout(self.left_form, 1)
        main_layout.addLayout(self.right_form, 1)

        self.setLayout(main_layout)
        self.setWindowTitle("Formulaire")

        # Charger le style depuis input.qss
        with open(resolve_resource_path("styles/input.qss"), "r", encoding="utf-8") as f:
            style = f.read()
            self.setStyleSheet(style)

    def set_responsable_username(self, username: str):
        self.responsable_input.setText(str(username or "").strip())

