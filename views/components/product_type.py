from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QInputDialog, QListWidgetItem
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from models.database_management import DatabaseManagement
from views.components.standard_invoice.products import StandardInvoiceProducts


class ProductType(QWidget):
    def __init__(self):
        super().__init__()

        # 
        DatabaseManagement.table_name = "product_type"
        self.db = DatabaseManagement()
        
        # cadre principale
        main_layout = QVBoxLayout()

        # cadre pour les boutons et label
        head_layout = QHBoxLayout()

        # Liste des types de produit
        self.type_list = QListWidget(self)
        self.type_list.setObjectName("listWidget")
        self.font = QFont("MS Gothic", weight=QFont.Bold)
        
        main_layout.addLayout(head_layout)
        main_layout.addWidget(self.type_list)
        

        # Boutons et label
        self.product_type_label = QLabel("Type de produit")
        self.del_btn = QPushButton("Supprimer")
        self.add_btn = QPushButton("Ajouter")

        head_layout.addWidget(self.product_type_label)
        head_layout.addWidget(self.del_btn)
        head_layout.addWidget(self.add_btn)

        self.setLayout(main_layout)

        # connexions
        self.add_btn.clicked.connect(self.add_type)
        self.del_btn.clicked.connect(self.del_type)
        self.type_list.itemSelectionChanged.connect(self.load_products)

        self.load_type()

    def load_type(self):
        self.type_list.clear()
        for type in self.db.get_all():
            item = QListWidgetItem(type['product_type_name'])
            item.setTextAlignment(Qt.AlignCenter)
            self.type_list.addItem(item)

    def load_products(self):
        pass

    def add_type(self):
        pass

    def del_type(self):
        pass