from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QInputDialog, QListWidgetItem
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt
from models.product_type_model import ProductTypeModel

class ProductTypeTemplate(QWidget):
    def __init__(self):
        super().__init__()

        # Widgets
        self.product_type_label = QLabel("Type de produit")
        self.product_type_delete_button = QPushButton("Supprimer")
        self.product_type_add_button = QPushButton("Ajouter")

        # Layout horizontal pour l'en-tête
        product_type_head = QHBoxLayout()
        product_type_head.addWidget(self.product_type_label)
        product_type_head.addWidget(self.product_type_delete_button)
        product_type_head.addWidget(self.product_type_add_button)

        # Layout vertical principal
        product_type_list = QVBoxLayout()
        product_type_list.addLayout(product_type_head)

        # Création de la liste
        self.listWidget = QListWidget(self)
        self.listWidget.setObjectName("listWidget")

        # Définition de la police
        self.font = QFont("MS Gothic", weight=QFont.Bold)

        # Récupération des items depuis la base
        items = self.get_item_from_database()

        # Boucle pour ajouter les items
        for text in items:
            self.add_item(text)

        # Ajout de la liste dans le layout principal
        product_type_list.addWidget(self.listWidget)

        # Associer le layout principal au widget
        self.setLayout(product_type_list)

        # Connexion des boutons
        self.product_type_add_button.clicked.connect(self.on_add_item)
        self.product_type_delete_button.clicked.connect(self.on_delete_item)

    def get_item_from_database(self):
        """Retourne la liste des noms de type de produit depuis la base."""
        product_types = ProductTypeModel.get_all()
        
        return [pt["product_type_name"] for pt in product_types]

    def add_item(self, text: str):
        """Ajoute un item formaté dans la liste."""
        item = QListWidgetItem(text)
        item.setTextAlignment(Qt.AlignCenter)
        item.setFont(self.font)
        self.listWidget.addItem(item)

    def on_add_item(self):
        """Demande un texte à l’utilisateur et ajoute l’item."""
        text, ok = QInputDialog.getText(self, "Nouvel item", "Nom du produit :")
        if ok and text.strip():
            self.add_item(text.strip())
            ProductTypeModel.insert({
                "product_type_name": text
            })

    def on_delete_item(self):
        """Supprime l’item sélectionné dans la liste."""
        selected_items = self.listWidget.selectedItems()
        if not selected_items:
            return  # Rien de sélectionné
        for item in selected_items:
            self.listWidget.takeItem(self.listWidget.row(item))
