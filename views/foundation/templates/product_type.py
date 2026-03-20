
    #     # Remplir la liste
    #     self.populate_list()

    #     product_type_list.addWidget(self.type_list)
    #     self.setLayout(product_type_list)

    #     # Connexions
    #     self.add_btn.clicked.connect(self.on_add_item)
    #     self.del_btn.clicked.connect(self.on_delete_item)

    #     self.type_list.itemClicked.connect(self.on_item_clicked)
        

    # def populate_list(self):
    #     """Charge les items depuis la base et les ajoute à la liste."""
    #     for pt in ProductTypeModel.get_all():
    #         self.add_item(pt["product_type_name"])

    # def get_product_type_id(self, item: QListWidgetItem):
    #     """Retourne l'id correspondant au nom de produit."""
    #     row = ProductTypeModel.fetch_row("id", "product_type_name", item.text())
    #     if row:  # row est un dict, ex: {"id": 3}
    #         return row["id"]
    #     return None

    # def add_item(self, text: str):
    #     """Ajoute un item formaté dans la liste."""
    #     item = QListWidgetItem(text)
    #     item.setTextAlignment(Qt.AlignCenter)
    #     item.setFont(self.font)
    #     self.type_list.addItem(item)

    # def on_add_item(self):
    #     """Demande un texte à l’utilisateur et ajoute l’item."""
    #     text, ok = QInputDialog.getText(self, "Nouvel item", "Nom du produit :")
    #     if ok and text.strip():
    #         self.add_item(text.strip())
    #         ProductTypeModel.insert({"product_type_name": text.strip()})

    # def on_delete_item(self):
    #     """Supprime l’item sélectionné dans la liste et dans la base."""
    #     for item in self.type_list.selectedItems():
    #         ProductTypeModel.delete({"product_type_name": item.text()})
    #         self.type_list.takeItem(self.type_list.row(item))

    # # Exemple : depuis ProductTypeTemplate
    # def on_item_clicked(self, item: QListWidgetItem):
    #     product_type_id = self.get_product_type_id(item)
    #     self.selected_product_type_id = product_type_id
    #     print(f"Item cliqué : {product_type_id}")

    #     # Créer ProductsTemplate avec l’ID
    #     ProductsTemplate(product_type_id=product_type_id)


        