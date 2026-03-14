from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTableWidget, QLineEdit, QLabel
)
from PySide6.QtCore import (Qt)

class ProductsTemplate(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("productType")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Layout principal
        main_layout = QVBoxLayout(self)

        # Bouton "Ajouter"
        self.btn_add = QPushButton("Ajouter")
        main_layout.addWidget(self.btn_add, alignment=Qt.AlignRight)

        # Table widget
        self.table = QTableWidget()
        self.table.setRowCount(5)   # par exemple 5 lignes de produits
        self.table.setColumnCount(10)

        self.table.setHorizontalHeaderLabels([
            "Désignation", "Ref.b.analyse", "N°Acte", "Physico",
            "Toxico", "Micro", "Sous total", "Modif", "Suppr", "Valider"
        ])

        # Remplir chaque ligne avec une boucle
        for row in range(self.table.rowCount()):
            # Colonnes de saisie
            for col in range(7):
                self.table.setCellWidget(row, col, QLineEdit())

            # Boutons d’action
            btn_modif = QPushButton("Modif")
            btn_suppr = QPushButton("Suppr")
            btn_valider = QPushButton("Valider")

            # Connecter chaque bouton à une fonction avec la ligne correspondante
            btn_modif.clicked.connect(lambda _, r=row: self.on_modif(r))
            btn_suppr.clicked.connect(lambda _, r=row: self.on_suppr(r))
            btn_valider.clicked.connect(lambda _, r=row: self.on_valider(r))

            self.table.setCellWidget(row, 7, btn_modif)
            self.table.setCellWidget(row, 8, btn_suppr)
            self.table.setCellWidget(row, 9, btn_valider)

        main_layout.addWidget(self.table)

        # Label montant
        self.lbl_montant = QLabel("Montant à payer:")
        main_layout.addWidget(self.lbl_montant)

        # Bouton enregistrer
        self.btn_save = QPushButton("Enregistrer")
        main_layout.addWidget(self.btn_save, alignment=Qt.AlignHCenter)

    # Fonctions reliées aux boutons
    def on_modif(self, row):
        print(f"Modifier ligne {row}")

    def on_suppr(self, row):
        print(f"Supprimer ligne {row}")

    def on_valider(self, row):
        print(f"Valider ligne {row}")