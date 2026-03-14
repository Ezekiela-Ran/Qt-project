from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTableWidget, QLineEdit, QLabel, QInputDialog
)
from PySide6.QtCore import Qt

class ProductsTemplate(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("productType")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        main_layout = QVBoxLayout(self)

        # Bouton "Ajouter"
        self.btn_add = QPushButton("Ajouter")
        self.btn_add.clicked.connect(self.on_add)
        main_layout.addWidget(self.btn_add, alignment=Qt.AlignRight)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Désignation", "Ref.b.analyse", "N°Acte", "Physico",
            "Toxico", "Micro", "Sous total", "", "", ""
        ])

        # Produits initiaux
        produits = []
        self.table.setRowCount(len(produits))
        for row, produit in enumerate(produits):
            self.add_row(row, produit)

        main_layout.addWidget(self.table)

        # Label montant
        self.lbl_montant = QLabel("Montant à payer:")
        main_layout.addWidget(self.lbl_montant)

        # Bouton enregistrer
        self.btn_save = QPushButton("Enregistrer")
        main_layout.addWidget(self.btn_save, alignment=Qt.AlignHCenter)

    def add_row(self, row, produit=""):
        lbl_designation = QLabel(produit)
        lbl_designation.setAlignment(Qt.AlignCenter)
        self.table.setCellWidget(row, 0, lbl_designation)

        for col in range(1, 7):
            self.table.setCellWidget(row, col, QLineEdit())

        btn_modif = QPushButton("Modif")
        btn_suppr = QPushButton("Suppr")
        btn_valider = QPushButton("Valider")

        btn_modif.clicked.connect(lambda _, r=row: self.on_modif(r))
        btn_suppr.clicked.connect(lambda _, r=row: self.on_suppr(r))
        btn_valider.clicked.connect(lambda _, r=row: self.on_valider(r))

        self.table.setCellWidget(row, 7, btn_modif)
        self.table.setCellWidget(row, 8, btn_suppr)
        self.table.setCellWidget(row, 9, btn_valider)

    def on_add(self):
        """Demande le nom du produit et ajoute une ligne"""
        produit, ok = QInputDialog.getText(self, "Nouveau produit", "Nom du produit :")
        if ok and produit.strip():
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.add_row(row, produit.strip())
            print(f"Ligne {row} ajoutée avec produit '{produit}'")

    def on_modif(self, row):
        print(f"Modifier ligne {row}")

    def on_suppr(self, row):
        self.table.removeRow(row)
        print(f"Ligne {row} supprimée")

    def on_valider(self, row):
        print(f"Valider ligne {row}")
