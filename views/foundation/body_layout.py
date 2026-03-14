from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from views.components.standard_invoice.product_type import StandardInvoiceProductType
from views.components.proforma_invoice.product_type import ProformaInvoiceProductType
from views.components.standard_invoice.products import StandardInvoiceProducts
from views.components.proforma_invoice.products import ProformaInvoiceProducts


class BodyLayout(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Layout principal
        self.body_layout = QtWidgets.QHBoxLayout(self)
        self.body_layout.setContentsMargins(0, 0, 0, 0)

        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Chargement du style QSS
        self._apply_stylesheet("styles/product_type.qss")

    def standard_invoice(self):
        # Section : type de produit
        self.standard_product_type = StandardInvoiceProductType()
        self.standard_product_type.setObjectName("productType")
        self.standard_product_type.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Section : liste des produits
        self.standard_products = StandardInvoiceProducts()

        # Ajout des widgets au layout avec proportions
        self.body_layout.addWidget(self.standard_product_type, 1)
        self.body_layout.addWidget(self.standard_products, 3)

    def proforma_invoice(self):
        # Section : type de produit
        self.proforma_product_type = ProformaInvoiceProductType()
        self.proforma_product_type.setObjectName("productType")
        self.proforma_product_type.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Section : liste des produits
        self.proforma_products = ProformaInvoiceProducts()

        # Ajout des widgets au layout avec proportions
        self.body_layout.addWidget(self.proforma_product_type, 1)
        self.body_layout.addWidget(self.proforma_products, 3)


    def _apply_stylesheet(self, path: str):
        """Charge et applique une feuille de style QSS depuis un fichier."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"Fichier de style introuvable : {path}")

