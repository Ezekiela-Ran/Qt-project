from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTableWidget, QLineEdit, QLabel, QInputDialog
)
from PySide6.QtCore import Qt
from models.products_model import ProductsModel

class ProductsTemplate(QWidget):
    def __init__(self, product_type_id=None):
        super().__init__()
        self.product_type_id = product_type_id  # <-- stocke l'ID reçu

        self.setObjectName("productType")
        self.setAttribute(Qt.WA_StyledBackground, True)

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
        main_layout.addWidget(self.table)

        # Mapping colonnes -> clés du modèle
        self.column_mapping = {
            1: "ref_b_analyse", 2: "num_act", 3: "physico",
            4: "toxico", 5: "micro", 6: "subtotal"
        }

        self.populate_table()

        # Label montant + bouton enregistrer
        main_layout.addWidget(QLabel("Montant à payer:"))
        main_layout.addWidget(QPushButton("Enregistrer"), alignment=Qt.AlignHCenter)

    def _make_line_edit(self, value=""):
        line_edit = QLineEdit()
        if value is not None:
            line_edit.setText(str(value))
        return line_edit

    def _default_product(self, name):
        return {
            "product_name": name, "ref_b_analyse": 0, "num_act": None,
            "physico": 0, "micro": 0, "toxico": 0, "subtotal": 0,
            "product_type_id": self.product_type_id
        }


    def _add_action_button(self, row, col, text, handler):
        btn = QPushButton(text)
        btn.clicked.connect(lambda _, r=row: handler(r))
        self.table.setCellWidget(row, col, btn)

    def populate_table(self):
        produits = ProductsModel.get_all()
        self.table.setRowCount(len(produits))
        for row, produit in enumerate(produits):
            self.add_row(row, produit)

    def add_row(self, row, produit):
        lbl_designation = QLabel(produit["product_name"])
        lbl_designation.setAlignment(Qt.AlignCenter)
        self.table.setCellWidget(row, 0, lbl_designation)

        for col, key in self.column_mapping.items():
            self.table.setCellWidget(row, col, self._make_line_edit(produit.get(key, "")))

        for col, text, handler in [(7, "Modif", self.on_modif),
                                   (8, "Suppr", self.on_suppr),
                                   (9, "Valider", self.on_valider)]:
            self._add_action_button(row, col, text, handler)

    def on_add(self):
        produit, ok = QInputDialog.getText(self, "Nouveau produit", "Nom du produit :")
        if ok and produit.strip():
            data = self._default_product(produit.strip())
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.add_row(row, data)
            ProductsModel.insert(data)
            print(f"Produit '{produit}' ajouté en DB et ligne {row} insérée.")

    def on_modif(self, row):
        print(f"Modifier ligne {row}")

    def on_suppr(self, row):
        product_name = self.table.cellWidget(row, 0).text()
        ProductsModel.delete({ProductsModel.name_column: product_name})
        self.table.removeRow(row)
        print(f"Produit '{product_name}' supprimé de la DB et ligne {row} retirée.")

    def on_valider(self, row):
        product_name = self.table.cellWidget(row, 0).text()
        data = {
            key: (int(widget.text()) if widget.text().isdigit() else widget.text().strip() or None)
            for col, key in self.column_mapping.items()
            if isinstance((widget := self.table.cellWidget(row, col)), QLineEdit)
        }
        ProductsModel.update(data, {"product_name": product_name})
        print("Données validées :", {"product_name": product_name, **data})
