from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

class ProductTypeTemplate(QWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.product_type_label = QLabel("Type de produit")
        self.product_type_button = QPushButton("Ajouter")

        # Layout horizontal pour l'en-tête
        product_type_head = QHBoxLayout()
        product_type_head.addWidget(self.product_type_label)
        product_type_head.addWidget(self.product_type_button)

        # Layout vertical principal
        product_type_list = QVBoxLayout()
        product_type_list.addLayout(product_type_head)

        # Création de la liste
        self.listWidget = QListWidget(self)
        self.listWidget.setObjectName("listWidget")

        # Définition de la police
        font = QFont("MS Gothic", weight=QFont.Bold)

        # Ajout d'un élément centré
        item = QListWidgetItem("Confiserie")
        item.setTextAlignment(Qt.AlignCenter)
        item.setFont(font)
        self.listWidget.addItem(item)

        # Ajout de la liste dans le layout principal
        product_type_list.addWidget(self.listWidget)

        # Associer le layout principal au widget
        self.setLayout(product_type_list)
