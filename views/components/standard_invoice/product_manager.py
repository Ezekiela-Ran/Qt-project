from PySide6.QtWidgets import (
    QListWidgetItem, QTableWidgetItem, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QTableWidget, QAbstractItemView, QLineEdit, QLabel, QInputDialog, 
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt


class ProductManager(QWidget):
    def __init__(self, db_manager):
        super().__init__()
        
        self.db = db_manager
        self.selected_products = {}  # dictionnaire {pid: True/False}


        # cadre principale
        main_layout = QHBoxLayout()

        # Types
        type_list_layout = QVBoxLayout()
        main_layout.addLayout(type_list_layout, 1)

        self.label = QLabel("Catégorie")
        self.add_type_btn = QPushButton("Ajouter")
        self.del_type_btn = QPushButton("Supprimer")
        self.type_list = QListWidget()

        type_list_layout.addWidget(self.label)
        type_list_layout.addWidget(self.add_type_btn)
        type_list_layout.addWidget(self.del_type_btn)
        type_list_layout.addWidget(self.type_list)
        
        # Produits
        product_list_layout = QVBoxLayout()
        main_layout.addLayout(product_list_layout, 3)

        self.add_product_btn = QPushButton("Ajouter")
        self.save_btn = QPushButton("Enregistrer")

        self.product_table = QTableWidget()
        self.product_table.setColumnCount(10)
        self.product_table.setHorizontalHeaderLabels(["Désignation", "Ref.b.analyse", "N°Acte", "Physico", "Toxico", "Micro", "Sous total", "Suppr", "Modif", "Select"])
        self.product_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        product_list_layout.addWidget(self.add_product_btn)
        product_list_layout.addWidget(self.product_table)
        product_list_layout.addWidget(self.save_btn)

        self.setLayout(main_layout)

        # Connexions
        self.add_type_btn.clicked.connect(self.add_type)
        self.del_type_btn.clicked.connect(self.del_type)
        self.add_product_btn.clicked.connect(self.add_product)
        self.save_btn.clicked.connect(self.save_products)
        self.type_list.itemSelectionChanged.connect(self.load_products)

        self.load_types()
    
    def load_types(self):
        self.type_list.clear()
        self.db.table_name = "product_type"
        for row in self.db.fetch_all():
            tid = row["id"]
            name = row["product_type_name"]
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, tid)  # stocker l'ID
            self.type_list.addItem(item)

    def add_type(self):
        self.db.table_name = "product_type"
        name, ok = QInputDialog.getText(self, "Nouveau Type", "Nom du type:")
        if ok and name:
            self.db.insert_type(name)
            self.load_types()

    def del_type(self):
        item = self.type_list.currentItem()
        if not item:
            return
        tid = item.data(Qt.UserRole)  # récupérer l'ID stocké
        self.db.delete_type(tid)
        self.load_types()
        self.product_table.setRowCount(0)

    def add_product(self):
        if not self.type_list.currentItem():
            return
        tid = self.type_list.currentItem().data(Qt.UserRole)
        name, ok = QInputDialog.getText(self, "Nouveau Produit", "Nom du produit:")
        if ok and name:
            pid = self.db.add_product(tid, name)
            self.add_product_row(pid, name, "0", "0", "0", "0", "0", "0")

    def add_product_row(self, pid, name, ref, num_act, physico, micro, toxico, subtotal):
        row = self.product_table.rowCount()
        self.product_table.insertRow(row)

        self.product_table.setItem(row, 0, QTableWidgetItem(name))
        self.product_table.item(row, 0).setData(Qt.UserRole, pid)

        ref_edit = QLineEdit(str(ref)); ref_edit.setReadOnly(True)
        num_act_edit = QLineEdit(str(num_act)); num_act_edit.setReadOnly(True)
        physico_edit = QLineEdit(str(physico)); physico_edit.setReadOnly(True)
        micro_edit = QLineEdit(str(micro)); micro_edit.setReadOnly(True)
        toxico_edit = QLineEdit(str(toxico)); toxico_edit.setReadOnly(True)
        subtotal_edit = QLineEdit(str(subtotal)); subtotal_edit.setReadOnly(True)

        self.product_table.setCellWidget(row, 1, ref_edit)
        self.product_table.setCellWidget(row, 2, num_act_edit)
        self.product_table.setCellWidget(row, 3, physico_edit)
        self.product_table.setCellWidget(row, 4, toxico_edit)
        self.product_table.setCellWidget(row, 5, micro_edit)
        self.product_table.setCellWidget(row, 6, subtotal_edit)

        btn_del = QPushButton("Suppr")
        btn_mod = QPushButton("Modifier")
        btn_sel = QPushButton("Select")

        self.product_table.setCellWidget(row, 7, btn_del)
        self.product_table.setCellWidget(row, 8, btn_mod)
        self.product_table.setCellWidget(row, 9, btn_sel)

        btn_del.clicked.connect(lambda: self.db.delete_product(pid) or self.product_table.removeRow(row))
        btn_mod.clicked.connect(lambda: self.toggle_edit(row))
        btn_sel.clicked.connect(lambda: self.toggle_select(pid, row))

        # Réappliquer style si déjà sélectionné
        if pid in self.selected_products and self.selected_products[pid]:
            btn_sel.setText("Annuler")
            self.apply_selection_style(row)

    def toggle_edit(self, row):
        widget = self.product_table.cellWidget(row, 1)
        btn = self.product_table.cellWidget(row, 8)
        if widget.isReadOnly():
            # Start edit
            btn.setText("Sauver")
            for col in [1, 2, 3, 4, 5, 6]:
                self.product_table.cellWidget(row, col).setReadOnly(False)
            self.product_table.cellWidget(row, 1).setFocus()
        else:
            # Save edit
            btn.setText("Modifier")
            pid = self.product_table.item(row, 0).data(Qt.UserRole)
            ref = self.product_table.cellWidget(row, 1).text()
            num_act = self.product_table.cellWidget(row, 2).text()
            physico = self.product_table.cellWidget(row, 3).text()
            toxico = self.product_table.cellWidget(row, 4).text()
            micro = self.product_table.cellWidget(row, 5).text()
            subtotal = self.product_table.cellWidget(row, 6).text()
            self.db.update_product(pid, ref, num_act, physico, toxico, micro, subtotal)
            for col in [1, 2, 3, 4, 5, 6]:
                self.product_table.cellWidget(row, col).setReadOnly(True)

    def toggle_select(self, pid, row):
        btn = self.product_table.cellWidget(row, 9)
        if btn.text() == "Select":
            btn.setText("Annuler")
            self.selected_products[pid] = True
            self.apply_selection_style(row)
        else:
            btn.setText("Select")
            self.selected_products[pid] = False
            self.clear_selection_style(row)

    def apply_selection_style(self, row):
        for col in range(self.product_table.columnCount()):
            item = self.product_table.item(row, col)
            if item:
                item.setBackground(Qt.green)
        for col in [1, 2, 3, 4, 5, 6]:
            widget = self.product_table.cellWidget(row, col)
            widget.setStyleSheet("background-color: lightgreen; border: 1px solid green;")

    def clear_selection_style(self, row):
        for col in range(self.product_table.columnCount()):
            item = self.product_table.item(row, col)
            if item:
                item.setBackground(Qt.white)
        for col in [1, 2, 3, 4, 5, 6]:
            widget = self.product_table.cellWidget(row, col)
            widget.setStyleSheet("")

    # Le bouton de suppression global de la liste de produits a été supprimé de l'UI.
    # La suppression se fait via le bouton "Suppr" de chaque ligne dans la table.

    def save_products(self):
        # Envoyer uniquement les produits sélectionnés
        selected_ids = [pid for pid, sel in self.selected_products.items() if sel]
        print("Produits sélectionnés à enregistrer:", selected_ids)
        # Faire un INSERT dans une table de commandes ou autre logique

    def load_products(self):
        self.product_table.setRowCount(0)
        if not self.type_list.currentItem():
            return
        tid = self.type_list.currentItem().data(Qt.UserRole)
        for pid, name, ref, num_act, physico, toxico, micro, subtotal in self.db.get_products_by_type(tid):
            self.add_product_row(pid, name, ref, num_act, physico, toxico, micro, subtotal)

