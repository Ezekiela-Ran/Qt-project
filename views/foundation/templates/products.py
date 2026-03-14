from PySide6.QtWidgets import (
    QWidget
)
from PySide6.QtCore import (Qt)

class ProductsTemplate(QWidget):
    def __init__(self):
        super().__init__()

        self.setObjectName("productType")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)