from PySide6.QtWidgets import QWidget, QHBoxLayout
from PySide6.QtCore import Qt
from views.components.standard_invoice.product_type import StandardInvoiceProductType
from views.components.standard_invoice.products import StandardInvoiceProducts


class BodyLayout(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Identifiant et style de base
        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Layout principal
        self.body_layout = QHBoxLayout(self)

        # Section : type de produit
        self.product_type = StandardInvoiceProductType()
        self.product_type.setObjectName("productType")
        self.product_type.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Section : liste des produits
        self.products = StandardInvoiceProducts()

        # Ajout des widgets au layout avec proportions
        self.body_layout.addWidget(self.product_type, stretch=1)
        self.body_layout.addWidget(self.products, stretch=3)

        # Chargement du style QSS
        self._apply_stylesheet("styles/product_type.qss")

    def _apply_stylesheet(self, path: str):
        """Charge et applique une feuille de style QSS depuis un fichier."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"Fichier de style introuvable : {path}")

