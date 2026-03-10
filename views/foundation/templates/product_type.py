from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout
)

class ProductTypeTemplate(QWidget):
    def __init__(self):
        super().__init__()

        self.product_type_label = QLabel("Type de produit")
        self.product_label = QLabel("Type de")
        self.produc_label = QLabel("Type de")
        self.produ_label = QLabel("Type de")
        self.prod_label = QLabel("Type de")
        self.pro_label = QLabel("Type de")
        self.pr_label = QLabel("Type de")
        self.p_label = QLabel("Type de")

        layout = QVBoxLayout()

        layout.addWidget(self.product_type_label)
        layout.addWidget(self.product_label)
        layout.addWidget(self.produc_label)
        layout.addWidget(self.produ_label)
        layout.addWidget(self.prod_label)
        layout.addWidget(self.pro_label)
        layout.addWidget(self.pr_label)
        layout.addWidget(self.p_label)

        self.setLayout(layout)