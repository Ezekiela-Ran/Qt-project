from PySide6.QtWidgets import (
    QListWidgetItem, QTableWidgetItem, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QTableWidget, QAbstractItemView, QLineEdit, QLabel, QInputDialog, 
)
from PySide6.QtGui import QFont, QIntValidator
from PySide6.QtCore import Qt, Signal


class ProductManager(QWidget):
    selection_changed = Signal()  # Signal émis quand la sélection change
    
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

        # Appliquer style aux boutons de catégorie
        button_style = "QPushButton { background-color: #1F4E79; color: white; padding: 4px 10px; border: none; border-radius: 4px; } QPushButton:hover { background-color: #163D62; }"
        self.add_type_btn.setStyleSheet(button_style)
        self.del_type_btn.setStyleSheet(button_style)

        type_list_layout.addWidget(self.label)
        type_list_layout.addWidget(self.add_type_btn)
        type_list_layout.addWidget(self.del_type_btn)
        type_list_layout.addWidget(self.type_list)
        
        # Produits
        product_list_layout = QVBoxLayout()
        main_layout.addLayout(product_list_layout, 3)

        self.add_product_btn = QPushButton("Ajouter")
        self.add_product_btn.setStyleSheet(button_style)

        self.product_table = QTableWidget()
        self.product_table.setColumnCount(10)
        self.product_table.setHorizontalHeaderLabels(["Désignation", "Ref.b.analyse", "N°Acte", "Physico", "Toxico", "Micro", "Sous total", "Suppr", "Modif", "Select"])
        self.product_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        add_button_layout = QHBoxLayout()
        add_button_layout.addStretch()
        add_button_layout.addWidget(self.add_product_btn)
        product_list_layout.addLayout(add_button_layout)
        product_list_layout.addWidget(self.product_table)

        self.setLayout(main_layout)

        # Connexions
        self.add_type_btn.clicked.connect(self.add_type)
        self.del_type_btn.clicked.connect(self.del_type)
        self.add_product_btn.clicked.connect(self.add_product)
        self.type_list.itemSelectionChanged.connect(self.load_products)

        self.load_types()
    
    def load_types(self):
        self.type_list.clear()
        self.db.table_name = "product_type"
        types = self.db.fetch_all()
        if not types:
            item = QListWidgetItem("Aucune catégorie disponible")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setTextAlignment(Qt.AlignCenter)
            self.type_list.addItem(item)
        else:
            for row in types:
                tid = row["id"]
                name = row["product_type_name"]
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, tid)  # stocker l'ID
                item.setTextAlignment(Qt.AlignCenter)
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

        # Set validators for integer fields
        int_validator = QIntValidator(0, 999999)  # Allow 0 to large number
        physico_edit.setValidator(int_validator)
        toxico_edit.setValidator(int_validator)
        micro_edit.setValidator(int_validator)
        ref_edit.setValidator(int_validator)
        num_act_edit.setValidator(int_validator)
        subtotal_edit.setValidator(int_validator)

        self.product_table.setCellWidget(row, 1, ref_edit)
        self.product_table.setCellWidget(row, 2, num_act_edit)
        self.product_table.setCellWidget(row, 3, physico_edit)
        self.product_table.setCellWidget(row, 4, toxico_edit)
        self.product_table.setCellWidget(row, 5, micro_edit)
        self.product_table.setCellWidget(row, 6, subtotal_edit)

        # Connect automatic recalculation et mise à jour DB sur modification des champs relevant du calcul.
        physico_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))
        toxico_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))
        micro_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))

        btn_del = QPushButton("Suppr")
        btn_mod = QPushButton("Modifier")
        btn_sel = QPushButton("Select")

        # Style boutons ligne produits
        row_button_style = "QPushButton { background-color: #2F5A8F; color: white; padding: 3px 8px; border: none; border-radius: 3px; } QPushButton:hover { background-color: #1E3F61; }"
        btn_del.setStyleSheet(row_button_style)
        btn_mod.setStyleSheet(row_button_style)
        btn_sel.setStyleSheet(row_button_style)

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
            # Start edit (subtotal reste non modifiable)
            btn.setText("Sauver")
            for col in [1, 2, 3, 4, 5]:
                self.product_table.cellWidget(row, col).setReadOnly(False)
            self.product_table.cellWidget(row, 1).setFocus()
        else:
            # Save edit
            btn.setText("Modifier")
            self.on_price_component_changed(row)
            for col in [1, 2, 3, 4, 5]:
                self.product_table.cellWidget(row, col).setReadOnly(True)

    def format_number(self, value):
        if value is None:
            return "0"
        try:
            v = float(value)
        except ValueError:
            return "0"
        if v.is_integer():
            return str(int(v))
        return str(v)

    def parse_number(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def on_price_component_changed(self, row):
        physico_widget = self.product_table.cellWidget(row, 3)
        toxico_widget = self.product_table.cellWidget(row, 4)
        micro_widget = self.product_table.cellWidget(row, 5)
        subtotal_widget = self.product_table.cellWidget(row, 6)

        physico = self.parse_number(physico_widget.text())
        toxico = self.parse_number(toxico_widget.text())
        micro = self.parse_number(micro_widget.text())

        subtotal_value = physico + toxico + micro
        subtotal_text = self.format_number(subtotal_value)

        subtotal_widget.setText(subtotal_text)

        # Mise à jour immédiate dans la base et interface
        pid = self.product_table.item(row, 0).data(Qt.UserRole)
        ref = self.product_table.cellWidget(row, 1).text()
        num_act = self.product_table.cellWidget(row, 2).text()

        self.db.update_product(pid, ref, num_act,
                               self.format_number(physico),
                               self.format_number(toxico),
                               self.format_number(micro),
                               subtotal_text)

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
        self.selection_changed.emit()  # Émettre le signal

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

    def disable_form_fields(self):
        # Accéder au formulaire
        main_layout = self.parent().parent()
        if hasattr(main_layout, 'head_layout') and hasattr(main_layout.head_layout, 'form'):
            form = main_layout.head_layout.form
            form.company_name_input.setEnabled(False)
            form.responsable_input.setEnabled(False)
            form.stat_input.setEnabled(False)
            form.nif_input.setEnabled(False)
            if hasattr(form, 'date_issue_input'):
                form.date_issue_input.setEnabled(False)
            if hasattr(form, 'date_result_input'):
                form.date_result_input.setEnabled(False)
            if hasattr(form, 'product_ref_input'):
                form.product_ref_input.setEnabled(False)
            if hasattr(form, 'date_input'):
                form.date_input.setEnabled(False)

    def enable_form_fields(self):
        # Accéder au formulaire
        main_layout = self.parent().parent()
        if hasattr(main_layout, 'head_layout') and hasattr(main_layout.head_layout, 'form'):
            form = main_layout.head_layout.form
            form.company_name_input.setEnabled(True)
            form.responsable_input.setEnabled(True)
            form.stat_input.setEnabled(True)
            form.nif_input.setEnabled(True)
            if hasattr(form, 'date_issue_input'):
                form.date_issue_input.setEnabled(True)
            if hasattr(form, 'date_result_input'):
                form.date_result_input.setEnabled(True)
            if hasattr(form, 'product_ref_input'):
                form.product_ref_input.setEnabled(True)
            if hasattr(form, 'date_input'):
                form.date_input.setEnabled(True)

    def select_products(self, product_ids):
        for pid in product_ids:
            self.selected_products[pid] = True
            # Trouver la ligne et appliquer la sélection
            for row in range(self.product_table.rowCount()):
                item_pid = self.product_table.item(row, 0).data(Qt.UserRole)
                if item_pid == pid:
                    btn = self.product_table.cellWidget(row, 9)
                    btn.setText("Annuler")
                    self.apply_selection_style(row)
                    break
        # la sélection ne désactive plus les champs du formulaire client
        return

    def load_products(self):
        self.product_table.setRowCount(0)
        if not self.type_list.currentItem():
            return
        tid = self.type_list.currentItem().data(Qt.UserRole)
        products = self.db.get_products_by_type(tid)
        if not products:
            self.product_table.insertRow(0)
            item = QTableWidgetItem("Aucun produit disponible pour cette catégorie")
            item.setTextAlignment(Qt.AlignCenter)
            self.product_table.setItem(0, 0, item)
            self.product_table.setSpan(0, 0, 1, self.product_table.columnCount())
        else:
            for product in products:
                pid = product['id']
                name = product['product_name']
                ref = product['ref_b_analyse']
                num_act = product['num_act']
                physico = product['physico']
                toxico = product['toxico']
                micro = product['micro']
                subtotal = product['subtotal']
                self.add_product_row(pid, name, ref, num_act, physico, toxico, micro, subtotal)

    def clear_selection(self):
        # Désélectionner tous les produits sélectionnés
        for pid, selected in list(self.selected_products.items()):
            if selected:
                # Trouver la ligne correspondante
                for row in range(self.product_table.rowCount()):
                    item_pid = self.product_table.item(row, 0)
                    if item_pid and item_pid.data(Qt.UserRole) == pid:
                        btn = self.product_table.cellWidget(row, 9)
                        if btn:
                            btn.setText("Select")
                        self.selected_products[pid] = False
                        self.clear_selection_style(row)
                        break
        self.enable_form_fields()
        self.selection_changed.emit()

