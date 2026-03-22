from PySide6.QtWidgets import (
    QListWidgetItem, QTableWidgetItem, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QTableWidget, QAbstractItemView, QLineEdit, QLabel, QInputDialog, 
)
from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt, Signal


class ProductManager(QWidget):
    selection_changed = Signal()  # Signal émis quand la sélection change
    
    def __init__(self, product_service, invoice_type="standard"):
        super().__init__()
        
        self.product_service = product_service
        self.invoice_type = invoice_type
        self.selected_products = {}  # dictionnaire {pid: True/False}
        self.selection_order = []  # ordre de sélection pour numéroter dynamiquement


        # cadre principale
        main_layout = QHBoxLayout()

        # Types
        type_list_layout = QVBoxLayout()
        main_layout.addLayout(type_list_layout, 1)

        self.label = QLabel("Catégorie")
        self.label.setObjectName("categoryTitle")
        self.add_type_btn = QPushButton("Ajouter")
        self.add_type_btn.setObjectName("categoryActionButton")
        self.del_type_btn = QPushButton("Supprimer")
        self.del_type_btn.setObjectName("categoryActionButton")
        self.type_list = QListWidget()

        type_list_layout.addWidget(self.label)
        type_list_layout.addWidget(self.add_type_btn)
        type_list_layout.addWidget(self.del_type_btn)
        type_list_layout.addWidget(self.type_list)
        
        # Produits
        product_list_layout = QVBoxLayout()
        main_layout.addLayout(product_list_layout, 3)

        self.add_product_btn = QPushButton("Ajouter")
        self.add_product_btn.setObjectName("categoryActionButton")

        self.product_table = QTableWidget()
        if self.invoice_type == "proforma":
            self.product_table.setColumnCount(9)
            self.product_table.setHorizontalHeaderLabels(["Désignation", "N°Acte", "Physico", "Toxico", "Micro", "Sous total", "Suppr", "Modif", "Select"])
        else:
            self.product_table.setColumnCount(10)
            self.product_table.setHorizontalHeaderLabels(["Désignation", "Ref.b.analyse", "N°Acte", "Physico", "Toxico", "Micro", "Sous total", "Suppr", "Modif", "Select"])
        self.product_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # Hide the reference column from the user but keep the widget so we can update it
        if self.invoice_type == "standard":
            self.product_table.setColumnHidden(1, True)

        add_button_layout = QHBoxLayout()
        add_button_layout.addStretch()
        add_button_layout.addWidget(self.add_product_btn)
        product_list_layout.addLayout(add_button_layout)
        product_list_layout.addWidget(self.product_table)

        self.setLayout(main_layout)
        self._apply_stylesheet("styles/product_manager.qss")

        # Connexions
        self.add_type_btn.clicked.connect(self.add_type)
        self.del_type_btn.clicked.connect(self.del_type)
        self.add_product_btn.clicked.connect(self.add_product)
        self.type_list.itemSelectionChanged.connect(self.load_products)

        self.load_types()
    
    def load_types(self):
        self.type_list.clear()
        self.product_service.db.table_name = "product_type"
        types = self.product_service.db.fetch_all()
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
        name, ok = QInputDialog.getText(self, "Nouveau Type", "Nom du type:")
        if ok and name:
            self.product_service.insert_type(name)
            self.load_types()

    def del_type(self):
        item = self.type_list.currentItem()
        if not item:
            return
        tid = item.data(Qt.UserRole)  # récupérer l'ID stocké
        try:
            self.product_service.delete_type(tid)
            self.load_types()
            self.product_table.setRowCount(0)
        except ValueError as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Suppression impossible", str(e))

    def add_product(self):
        if not self.type_list.currentItem():
            return
        tid = self.type_list.currentItem().data(Qt.UserRole)
        name, ok = QInputDialog.getText(self, "Nouveau Produit", "Nom du produit:")
        if ok and name:
            pid = self.product_service.add_product(tid, name)
            self.add_product_row(pid, name, "0", "0", "0", "0", "0", "0")

    def add_product_row(self, pid, name, ref, num_act, physico, toxico, micro, subtotal):
        row = self.product_table.rowCount()
        self.product_table.insertRow(row)

        self.product_table.setItem(row, 0, QTableWidgetItem(name))
        self.product_table.item(row, 0).setData(Qt.UserRole, pid)

        if self.invoice_type == "standard":
            ref_edit = QLineEdit(str(ref)); ref_edit.setReadOnly(True)
            self.product_table.setCellWidget(row, 1, ref_edit)

        num_act_edit = QLineEdit(str(num_act)); num_act_edit.setReadOnly(True)
        physico_edit = QLineEdit(str(physico)); physico_edit.setReadOnly(True)
        toxico_edit = QLineEdit(str(toxico)); toxico_edit.setReadOnly(True)
        micro_edit = QLineEdit(str(micro)); micro_edit.setReadOnly(True)
        subtotal_edit = QLineEdit(str(subtotal)); subtotal_edit.setReadOnly(True)

        # Set validators for integer fields
        int_validator = QIntValidator(0, 999999)  # Allow 0 to large number
        physico_edit.setValidator(int_validator)
        toxico_edit.setValidator(int_validator)
        micro_edit.setValidator(int_validator)
        if self.invoice_type == "standard":
            ref_edit.setValidator(int_validator)
        num_act_edit.setValidator(int_validator)
        subtotal_edit.setValidator(int_validator)

        if self.invoice_type == "standard":
            self.product_table.setCellWidget(row, 2, num_act_edit)
            self.product_table.setCellWidget(row, 3, physico_edit)
            self.product_table.setCellWidget(row, 4, toxico_edit)
            self.product_table.setCellWidget(row, 5, micro_edit)
            self.product_table.setCellWidget(row, 6, subtotal_edit)
        else:
            self.product_table.setCellWidget(row, 1, num_act_edit)
            self.product_table.setCellWidget(row, 2, physico_edit)
            self.product_table.setCellWidget(row, 3, toxico_edit)
            self.product_table.setCellWidget(row, 4, micro_edit)
            self.product_table.setCellWidget(row, 5, subtotal_edit)

        # Connect automatic recalculation et mise à jour DB sur modification des champs relevant du calcul.
        physico_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))
        toxico_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))
        micro_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))

        btn_del = QPushButton("Suppr")
        btn_mod = QPushButton("Modifier")
        btn_sel = QPushButton("Select")
        btn_del.setObjectName("rowActionButton")
        btn_mod.setObjectName("rowActionButton")
        btn_sel.setObjectName("rowActionButton")

        # Positions des boutons selon le type
        if self.invoice_type == "standard":
            btn_del_col = 7
            btn_mod_col = 8
            btn_sel_col = 9
        else:  # proforma
            btn_del_col = 6
            btn_mod_col = 7
            btn_sel_col = 8

        self.product_table.setCellWidget(row, btn_del_col, btn_del)
        self.product_table.setCellWidget(row, btn_mod_col, btn_mod)
        self.product_table.setCellWidget(row, btn_sel_col, btn_sel)

        btn_del.clicked.connect(lambda: self.product_service.delete_product(pid) or self.product_table.removeRow(row))
        btn_mod.clicked.connect(lambda: self.toggle_edit(row))
        btn_sel.clicked.connect(lambda: self.toggle_select(pid, row))

        # Réappliquer style si déjà sélectionné
        if pid in self.selected_products and self.selected_products[pid]:
            btn_sel.setText("Annuler")
            self.apply_selection_style(row)

    def toggle_edit(self, row):
        if self.invoice_type == "standard":
            widget_col = 1
            btn_col = 8
            editable_cols = [1, 2, 3, 4, 5]
            focus_col = 1
        else:
            widget_col = 1
            btn_col = 7
            editable_cols = [1, 2, 3, 4]
            focus_col = 1
        widget = self.product_table.cellWidget(row, widget_col)
        btn = self.product_table.cellWidget(row, btn_col)
        if widget.isReadOnly():
            # Start edit (subtotal reste non modifiable)
            btn.setText("Sauver")
            for col in editable_cols:
                self.product_table.cellWidget(row, col).setReadOnly(False)
            self.product_table.cellWidget(row, focus_col).setFocus()
        else:
            # Save edit
            btn.setText("Modifier")
            self.on_price_component_changed(row)
            for col in editable_cols:
                self.product_table.cellWidget(row, col).setReadOnly(True)

    def format_number(self, value):
        if value is None:
            return "0 Ariary"
        try:
            v = float(value)
        except ValueError:
            return "0 Ariary"
        if v.is_integer():
            formatted = f"{int(v):,}".replace(",", " ")
            return f"{formatted} Ariary"
        formatted = f"{v:,.2f}".replace(",", " ")
        return f"{formatted} Ariary"

    def parse_number(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def on_price_component_changed(self, row):
        if self.invoice_type == "standard":
            ref_col = 1
            num_act_col = 2
            physico_col = 3
            toxico_col = 4
            micro_col = 5
            subtotal_col = 6
        else:  # proforma
            ref_col = None
            num_act_col = 1
            physico_col = 2
            toxico_col = 3
            micro_col = 4
            subtotal_col = 5

        physico_widget = self.product_table.cellWidget(row, physico_col)
        toxico_widget = self.product_table.cellWidget(row, toxico_col)
        micro_widget = self.product_table.cellWidget(row, micro_col)
        subtotal_widget = self.product_table.cellWidget(row, subtotal_col)

        physico = self.parse_number(physico_widget.text())
        toxico = self.parse_number(toxico_widget.text())
        micro = self.parse_number(micro_widget.text())

        subtotal_value = physico + toxico + micro
        subtotal_text = self.format_number(subtotal_value)

        subtotal_widget.setText(subtotal_text)

        # Mise à jour immédiate dans la base et interface
        pid = self.product_table.item(row, 0).data(Qt.UserRole)
        if self.invoice_type == "standard":
            ref = int(self.product_table.cellWidget(row, ref_col).text() or 0)
        else:
            ref = 0  # Not used for proforma
        num_act = self.product_table.cellWidget(row, num_act_col).text()

        # Persist numeric components but DO NOT change ref here (ref is managed in-memory until save)
        self.product_service.update_product(pid, ref, num_act,
                       int(physico),
                       int(toxico),
                       int(micro),
                       int(subtotal_value),
                       update_ref=False)

    def toggle_select(self, pid, row):
        btn_col = 9 if self.invoice_type == "standard" else 8
        btn = self.product_table.cellWidget(row, btn_col)
        ref_col = 1 if self.invoice_type == "standard" else None
        currently_selected = bool(self.selected_products.get(pid, False))

        if not currently_selected:
            # Select: mark and append to order
            if btn:
                btn.setText("Annuler")
            self.selected_products[pid] = True
            if pid not in self.selection_order:
                self.selection_order.append(pid)
            self.apply_selection_style(row)
        else:
            # Deselect: unmark and remove from order
            if btn:
                btn.setText("Select")
            self.selected_products[pid] = False
            if pid in self.selection_order:
                self.selection_order.remove(pid)
            self.clear_selection_style(row)

        # Renumber UI refs dynamically (1..n) according to selection_order
        self._renumber_selection_ui()
        self.selection_changed.emit()

    def _renumber_selection_ui(self):
        # Assign contiguous refs 1..n to selected products based on selection_order
        # Rows not selected get 0
        # Build mapping pid -> assigned ref
        assigned = {pid: idx + 1 for idx, pid in enumerate(self.selection_order)}
        for row in range(self.product_table.rowCount()):
            item = self.product_table.item(row, 0)
            if not item:
                continue
            pid = item.data(Qt.UserRole)
            if pid is None:
                continue
            if self.invoice_type == 'standard':
                ref_widget = self.product_table.cellWidget(row, 1)
                if ref_widget is None:
                    continue
                if pid in assigned:
                    ref_widget.setText(str(assigned[pid]))
                else:
                    ref_widget.setText("0")

    def apply_selection_style(self, row):
        for col in range(self.product_table.columnCount()):
            item = self.product_table.item(row, col)
            if item:
                item.setBackground(Qt.green)
        if self.invoice_type == "standard":
            editable_cols = [1, 2, 3, 4, 5]
        else:
            editable_cols = [1, 2, 3, 4]
        for col in editable_cols:
            widget = self.product_table.cellWidget(row, col)
            if widget:
                widget.setProperty("selectedRow", True)
                widget.style().unpolish(widget)
                widget.style().polish(widget)

    def clear_selection_style(self, row):
        for col in range(self.product_table.columnCount()):
            item = self.product_table.item(row, col)
            if item:
                item.setBackground(Qt.white)
        if self.invoice_type == "standard":
            editable_cols = [1, 2, 3, 4, 5]
        else:
            editable_cols = [1, 2, 3, 4]
        for col in editable_cols:
            widget = self.product_table.cellWidget(row, col)
            if widget:
                widget.setProperty("selectedRow", False)
                widget.style().unpolish(widget)
                widget.style().polish(widget)

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
        # Select given products and maintain selection order. Do not persist refs here.
        for pid in product_ids:
            if self.selected_products.get(pid, False):
                continue
            self.selected_products[pid] = True
            if pid not in self.selection_order:
                self.selection_order.append(pid)
            # Trouver la ligne et appliquer la sélection UI
            for row in range(self.product_table.rowCount()):
                row_item = self.product_table.item(row, 0)
                if not row_item:
                    continue
                item_pid = row_item.data(Qt.UserRole)
                if item_pid == pid:
                    btn_col = 9 if self.invoice_type == "standard" else 8
                    btn = self.product_table.cellWidget(row, btn_col)
                    if btn:
                        btn.setText("Annuler")
                        self.apply_selection_style(row)
                    break
        # Renumber UI refs after bulk selection
        self._renumber_selection_ui()
        # la sélection ne désactive plus les champs du formulaire client
        return

    def load_products(self):
        self.product_table.setRowCount(0)
        if not self.type_list.currentItem():
            return
        tid = self.type_list.currentItem().data(Qt.UserRole)
        products = self.product_service.get_products_by_type(tid)
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
                        btn_col = 9 if self.invoice_type == "standard" else 8
                        btn = self.product_table.cellWidget(row, btn_col)
                        if btn:
                            btn.setText("Select")
                        # decrement ref for standard invoices
                        if self.invoice_type == "standard":
                            ref_widget = self.product_table.cellWidget(row, 1)
                            if ref_widget is None:
                                continue
                            try:
                                cur = int(ref_widget.text() or 0)
                            except Exception:
                                cur = 0
                            # Deselect: free the reference (set to 0)
                            new = 0
                            ref_widget.setText("0")
                            # persist
                            num_act = self.product_table.cellWidget(row, 2).text()
                            physico = int(self.product_table.cellWidget(row, 3).text() or 0)
                            toxico = int(self.product_table.cellWidget(row, 4).text() or 0)
                            micro = int(self.product_table.cellWidget(row, 5).text() or 0)
                            subtotal = int((physico + toxico + micro) or 0)
                            try:
                                    # Do not persist ref to DB on UI deselection here
                                    self.product_service.update_product(pid, new, num_act, physico, toxico, micro, subtotal, update_ref=False)
                            except Exception:
                                pass
                        self.selected_products[pid] = False
                        self.clear_selection_style(row)
                        # also remove from selection order
                        if pid in self.selection_order:
                            self.selection_order.remove(pid)
                        break
        self.enable_form_fields()
        # Renumber UI refs to reflect cleared selections
        self._renumber_selection_ui()
        self.selection_changed.emit()

    def _apply_stylesheet(self, stylesheet_path):
        try:
            with open(stylesheet_path, "r", encoding="utf-8") as file:
                self.setStyleSheet(file.read())
        except FileNotFoundError:
            print(f"Stylesheet {stylesheet_path} not found.")

