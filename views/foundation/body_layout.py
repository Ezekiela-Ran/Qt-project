from PySide6 import QtWidgets,QtCore
from views.components.standard_invoice.product_type import StandardInvoiceProductType
from views.components.standard_invoice.products import StandardInvoiceProducts

class BodyLayout(QtWidgets.QWidget):
    def __init__(self,parent):
        super().__init__(parent)

        self.setObjectName("card")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)   

        self.body_layout = QtWidgets.QVBoxLayout(self)
        

        self.product_type = StandardInvoiceProductType()
        self.product_type.setObjectName("productType")
        self.product_type.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        self.product_type.setMaximumWidth(400)
        self.products = StandardInvoiceProducts()

        self.body_layout.addWidget(self.product_type, 1)
        self.body_layout.addWidget(self.products, 1)

        with open("styles/product_type.qss", "r") as f:
            self.setStyleSheet(f.read())
