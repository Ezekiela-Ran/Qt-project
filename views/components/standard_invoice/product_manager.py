from PySide6.QtWidgets import (
    QListWidgetItem, QTableWidgetItem, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QTableWidget, QAbstractItemView, QLineEdit, QLabel, QInputDialog, QMessageBox,
)
from PySide6.QtGui import QIntValidator, QColor
from PySide6.QtCore import Qt, Signal, QTimer, QSignalBlocker
from utils.path_utils import resolve_resource_path
from views.foundation.globals import GlobalVariable


CATALOG_REFRESH_INTERVAL_MS = 5000


class ProductManager(QWidget):
    selection_changed = Signal()  # Signal émis quand la sélection change
    
    def __init__(self, product_service, invoice_type="standard"):
        super().__init__()
        
        self.product_service = product_service
        self.invoice_type = invoice_type
        self.selected_products = {}  # dictionnaire {pid: True/False}
        self.selection_order = []  # ordre de sélection pour numéroter dynamiquement
        self.selected_refs = {}  # dictionnaire {pid: ref_b_analyse} pour standard
        self.selected_num_acts = {}  # dictionnaire {pid: num_act} pour standard
        self.loaded_record_locked = False
        self.can_manage_catalog = GlobalVariable.is_admin()
        self.catalog_signature = None
        self.active_edit_row = None
        self.pending_catalog_reload = False
        self.pending_catalog_signature = None

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)

        self.catalog_notification = QLabel("")
        self.catalog_notification.setVisible(False)
        self.catalog_notification.setWordWrap(True)
        self.catalog_notification.setAlignment(Qt.AlignCenter)
        self.catalog_notification.setStyleSheet(
            "background-color: #264b2f; color: white; border: 1px solid #4b8a58; border-radius: 4px; padding: 6px 10px;"
        )
        root_layout.addWidget(self.catalog_notification)

        # cadre principale
        main_layout = QHBoxLayout()
        root_layout.addLayout(main_layout)

        # Types
        type_list_layout = QVBoxLayout()
        main_layout.addLayout(type_list_layout, 1)

        self.label = QLabel("Catégorie")
        self.label.setObjectName("categoryTitle")
        self.add_type_btn = QPushButton("Ajouter")
        self.add_type_btn.setObjectName("categoryActionButton")
        self.edit_type_btn = QPushButton("Modifier")
        self.edit_type_btn.setObjectName("categoryActionButton")
        self.del_type_btn = QPushButton("Supprimer")
        self.del_type_btn.setObjectName("categoryActionButton")
        self.type_list = QListWidget()

        type_list_layout.addWidget(self.label)
        type_list_layout.addWidget(self.add_type_btn)
        type_list_layout.addWidget(self.edit_type_btn)
        type_list_layout.addWidget(self.del_type_btn)
        type_list_layout.addWidget(self.type_list)
        
        # Produits
        product_list_layout = QVBoxLayout()
        main_layout.addLayout(product_list_layout, 3)

        self.add_product_btn = QPushButton("Ajouter")
        self.add_product_btn.setObjectName("categoryActionButton")

        self.product_table = QTableWidget()
        if self.invoice_type == "proforma":
            self.product_table.setColumnCount(8)
            self.product_table.setHorizontalHeaderLabels(["Désignation", "Physico", "Toxico", "Micro", "Sous total", "Suppr", "Modif", "Choisir"])
        else:
            self.product_table.setColumnCount(10)
            self.product_table.setHorizontalHeaderLabels(["Désignation", "Ref.b.analyse", "N°Acte", "Physico", "Toxico", "Micro", "Sous total", "Suppr", "Modif", "Choisir"])
        self.product_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # Hide the reference column from the user but keep the widget so we can update it
        if self.invoice_type == "standard":
            self.product_table.setColumnHidden(1, True)

        add_button_layout = QHBoxLayout()
        add_button_layout.addStretch()
        add_button_layout.addWidget(self.add_product_btn)
        product_list_layout.addLayout(add_button_layout)
        product_list_layout.addWidget(self.product_table)

        self._apply_stylesheet("styles/product_manager.qss")
        self.catalog_notice_timer = QTimer(self)
        self.catalog_notice_timer.setSingleShot(True)
        self.catalog_notice_timer.timeout.connect(self.catalog_notification.hide)
        self.catalog_refresh_timer = None

        # Connexions
        self.add_type_btn.clicked.connect(self.add_type)
        self.edit_type_btn.clicked.connect(self.edit_type)
        self.del_type_btn.clicked.connect(self.del_type)
        self.add_product_btn.clicked.connect(self.add_product)
        self.type_list.itemSelectionChanged.connect(self.load_products)

        self._apply_role_permissions()
        has_selection = self.load_types()
        if has_selection:
            self.load_products()

        self.catalog_signature = self._safe_catalog_signature()
        self.catalog_refresh_timer = QTimer(self)
        self.catalog_refresh_timer.setInterval(CATALOG_REFRESH_INTERVAL_MS)
        self.catalog_refresh_timer.timeout.connect(self.refresh_catalog_silently)
        self.catalog_refresh_timer.start()

    def _apply_role_permissions(self):
        self.add_type_btn.setVisible(self.can_manage_catalog)
        self.edit_type_btn.setVisible(self.can_manage_catalog)
        self.del_type_btn.setVisible(self.can_manage_catalog)
        self.add_product_btn.setVisible(self.can_manage_catalog)
    
    def load_types(self, selected_type_id=None):
        if selected_type_id is None and self.type_list.currentItem():
            selected_type_id = self.type_list.currentItem().data(Qt.UserRole)

        self.type_list.blockSignals(True)
        self.type_list.clear()
        self.product_service.db.table_name = "product_type"
        types = self.product_service.db.fetch_all()
        if not types:
            item = QListWidgetItem("Aucune catégorie disponible")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setTextAlignment(Qt.AlignCenter)
            self.type_list.addItem(item)
            self.type_list.blockSignals(False)
            return False
        else:
            for row in types:
                tid = row["id"]
                name = row["product_type_name"]
                item = QListWidgetItem(name)
                item.setData(Qt.UserRole, tid)  # stocker l'ID
                item.setTextAlignment(Qt.AlignCenter)
                self.type_list.addItem(item)

        if selected_type_id is not None and self._set_current_type_by_id(selected_type_id):
            self.type_list.blockSignals(False)
            return True

        for index in range(self.type_list.count()):
            item = self.type_list.item(index)
            if item and item.data(Qt.UserRole) is not None:
                self.type_list.setCurrentRow(index)
                self.type_list.blockSignals(False)
                return True
        self.type_list.blockSignals(False)
        return False

    def _set_current_type_by_id(self, type_id):
        for index in range(self.type_list.count()):
            item = self.type_list.item(index)
            if item and item.data(Qt.UserRole) == type_id:
                self.type_list.setCurrentRow(index)
                return True
        return False

    def add_type(self):
        if not self.can_manage_catalog:
            return
        name, ok = QInputDialog.getText(self, "Nouveau Type", "Nom du type:")
        if ok and name:
            new_type_id = self.product_service.insert_type(name)
            self._after_local_catalog_change(selected_type_id=new_type_id)

    def edit_type(self):
        if not self.can_manage_catalog:
            return
        item = self.type_list.currentItem()
        if not item:
            return
        tid = item.data(Qt.UserRole)
        if tid is None:
            return
        current_name = item.text().strip()
        name, ok = QInputDialog.getText(self, "Modifier le type", "Nom du type:", text=current_name)
        name = (name or "").strip()
        if ok and name:
            self.product_service.update_type_name(tid, name)
            self._after_local_catalog_change(selected_type_id=tid)

    def del_type(self):
        if not self.can_manage_catalog:
            return
        item = self.type_list.currentItem()
        if not item:
            return
        tid = item.data(Qt.UserRole)  # récupérer l'ID stocké
        try:
            self.product_service.delete_type(tid)
            self._after_local_catalog_change()
        except ValueError as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Suppression impossible", str(e))

    def add_product(self):
        if not self.can_manage_catalog:
            return
        if self.loaded_record_locked:
            return
        if not self.type_list.currentItem():
            return
        tid = self.type_list.currentItem().data(Qt.UserRole)
        name, ok = QInputDialog.getText(self, "Nouveau Produit", "Nom du produit:")
        if ok and name:
            self.product_service.add_product(tid, name)
            self._after_local_catalog_change(selected_type_id=tid)

    def add_product_row(self, pid, name, ref, num_act, physico, toxico, micro, subtotal):
        row = self.product_table.rowCount()
        self.product_table.insertRow(row)

        self.product_table.setItem(row, 0, QTableWidgetItem(name))
        self.product_table.item(row, 0).setData(Qt.UserRole, pid)

        if self.invoice_type == "standard":
            ref_edit = QLineEdit(str(ref)); ref_edit.setReadOnly(True)
            self.product_table.setCellWidget(row, 1, ref_edit)
            num_act_edit = QLineEdit(self._display_num_act(num_act)); num_act_edit.setReadOnly(True)
            physico_edit = QLineEdit(self.format_number(physico)); physico_edit.setReadOnly(True)
            toxico_edit = QLineEdit(self.format_number(toxico)); toxico_edit.setReadOnly(True)
            micro_edit = QLineEdit(self.format_number(micro)); micro_edit.setReadOnly(True)
            subtotal_edit = QLineEdit(self.format_number(subtotal)); subtotal_edit.setReadOnly(True)

            # Set validators for integer fields
            int_validator = QIntValidator(0, 999999)
            physico_edit.setValidator(int_validator)
            toxico_edit.setValidator(int_validator)
            micro_edit.setValidator(int_validator)
            ref_edit.setValidator(int_validator)
            subtotal_edit.setValidator(int_validator)

            self.product_table.setCellWidget(row, 2, num_act_edit)
            self.product_table.setCellWidget(row, 3, physico_edit)
            self.product_table.setCellWidget(row, 4, toxico_edit)
            self.product_table.setCellWidget(row, 5, micro_edit)
            self.product_table.setCellWidget(row, 6, subtotal_edit)

            # Positions des boutons pour standard
            btn_del_col = 7
            btn_mod_col = 8
            btn_sel_col = 9
        else:  # proforma
            physico_edit = QLineEdit(self.format_number(physico)); physico_edit.setReadOnly(True)
            toxico_edit = QLineEdit(self.format_number(toxico)); toxico_edit.setReadOnly(True)
            micro_edit = QLineEdit(self.format_number(micro)); micro_edit.setReadOnly(True)
            subtotal_edit = QLineEdit(self.format_number(subtotal)); subtotal_edit.setReadOnly(True)

            # Set validators for integer fields
            int_validator = QIntValidator(0, 999999)
            physico_edit.setValidator(int_validator)
            toxico_edit.setValidator(int_validator)
            micro_edit.setValidator(int_validator)
            subtotal_edit.setValidator(int_validator)

            self.product_table.setCellWidget(row, 1, physico_edit)
            self.product_table.setCellWidget(row, 2, toxico_edit)
            self.product_table.setCellWidget(row, 3, micro_edit)
            self.product_table.setCellWidget(row, 4, subtotal_edit)

            # Positions des boutons pour proforma
            btn_del_col = 5
            btn_mod_col = 6
            btn_sel_col = 7

        # Connect automatic recalculation et mise à jour DB sur modification des champs relevant du calcul.
        physico_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))
        toxico_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))
        micro_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))

        btn_del = QPushButton("Suppr")
        btn_mod = QPushButton("Modifier")
        btn_sel = QPushButton("Choisir")
        btn_del.setObjectName("rowActionButton")
        btn_mod.setObjectName("rowActionButton")
        btn_sel.setObjectName("rowActionButton")

        self.product_table.setCellWidget(row, btn_del_col, btn_del)
        self.product_table.setCellWidget(row, btn_mod_col, btn_mod)
        self.product_table.setCellWidget(row, btn_sel_col, btn_sel)

        btn_del.clicked.connect(lambda: self.delete_product_row(pid, row))
        btn_mod.clicked.connect(self.toggle_edit_from_sender)
        btn_sel.clicked.connect(lambda: self.toggle_select(pid, row))

        btn_del.setEnabled(self.can_manage_catalog and not self.loaded_record_locked)
        btn_mod.setEnabled(self.can_manage_catalog)
        btn_sel.setEnabled(not self.loaded_record_locked)

        # Réappliquer style si déjà sélectionné
        if pid in self.selected_products and self.selected_products[pid]:
            btn_sel.setText("Annuler")
            if self.invoice_type == "standard":
                selected_num_act = self.selected_num_acts.get(pid)
                if selected_num_act is not None:
                    num_act_edit.setText(selected_num_act)
            self.apply_selection_style(row)

    def toggle_edit(self, row):
        if not self.can_manage_catalog:
            return
        if self.active_edit_row is not None and self.active_edit_row != row:
            return
        designation_item = self.product_table.item(row, 0)
        if designation_item is None:
            return
        pid = designation_item.data(Qt.UserRole)
        if pid is None:
            return
        if self.invoice_type == "standard":
            # Col 1 (ref) est cachée — utiliser col 2 (N°Acte, visible) comme sentinel
            widget_col = 2
            btn_col = 8
            editable_cols = [1, 2, 3, 4, 5]
            amount_cols = [3, 4, 5]
            focus_col = 2
        else:  # proforma
            widget_col = 1
            btn_col = 6
            editable_cols = [1, 2, 3]
            amount_cols = [1, 2, 3]
            focus_col = 1
        widget = self.product_table.cellWidget(row, widget_col)
        btn = self.product_table.cellWidget(row, btn_col)
        if widget.isReadOnly():
            # Start edit (subtotal reste non modifiable)
            self.active_edit_row = row
            btn.setText("Sauver")
            self._begin_designation_edit(row)
            # Remove display formatting while editing amount fields.
            for col in amount_cols:
                amount_widget = self.product_table.cellWidget(row, col)
                if amount_widget:
                    self._set_line_edit_text(amount_widget, str(int(self.parse_number(amount_widget.text()))))
            for col in editable_cols:
                self.product_table.cellWidget(row, col).setReadOnly(False)
            self.product_table.cellWidget(row, focus_col).setFocus()
        else:
            # Save edit
            if self.invoice_type == "standard" and not self.validate_num_act_row(row):
                self.product_table.cellWidget(row, 2).setFocus()
                return
            if not self._save_designation_edit(row, pid):
                return
            self.on_price_component_changed(row)
            self._persist_row_changes(row, pid)
            btn.setText("Modifier")
            for col in amount_cols:
                amount_widget = self.product_table.cellWidget(row, col)
                if amount_widget:
                    self._set_line_edit_text(amount_widget, self.format_number(amount_widget.text()))
            for col in editable_cols:
                self.product_table.cellWidget(row, col).setReadOnly(True)
            self.active_edit_row = None
            if self.selected_products.get(pid, False):
                self.selection_changed.emit()
            self._flush_pending_catalog_reload()

    def toggle_edit_from_sender(self):
        if not self.can_manage_catalog:
            return
        button = self.sender()
        if button is None:
            return
        btn_col = 8 if self.invoice_type == "standard" else 6
        row = self._find_row_for_button(button, btn_col)
        if row < 0:
            return
        self.toggle_edit(row)

    def _find_row_for_button(self, button, column):
        for row in range(self.product_table.rowCount()):
            if self.product_table.cellWidget(row, column) is button:
                return row
        return -1

    def _find_row_for_product(self, product_id):
        for row in range(self.product_table.rowCount()):
            item = self.product_table.item(row, 0)
            if item and item.data(Qt.UserRole) == product_id:
                return row
        return -1

    def _is_edit_active(self):
        return self.active_edit_row is not None

    def _set_line_edit_text(self, widget, text):
        if widget is None:
            return
        blocker = QSignalBlocker(widget)
        try:
            widget.setText(text)
        finally:
            del blocker

    def _flush_pending_catalog_reload(self):
        if not self.pending_catalog_reload or self._is_edit_active():
            return

        previous_signature = self.catalog_signature
        self.pending_catalog_reload = False
        self.pending_catalog_signature = None

        latest_signature = self._safe_catalog_signature()
        if latest_signature is None or latest_signature == previous_signature:
            return

        self.catalog_signature = latest_signature
        self._reload_catalog_preserving_state()
        self._show_catalog_notification("Le catalogue a ete mis a jour automatiquement.")

    def _mark_catalog_reload_pending(self, latest_signature=None):
        self.pending_catalog_reload = True
        self.pending_catalog_signature = latest_signature or self._safe_catalog_signature()

    def _restore_row_from_database(self, row, pid):
        product = self.product_service.get_product_by_id(pid)
        if not product:
            return

        item = self.product_table.item(row, 0)
        if item is not None:
            item.setText(product["product_name"])

        if self.invoice_type == "standard":
            ref_widget = self.product_table.cellWidget(row, 1)
            num_act_widget = self.product_table.cellWidget(row, 2)
            physico_widget = self.product_table.cellWidget(row, 3)
            toxico_widget = self.product_table.cellWidget(row, 4)
            micro_widget = self.product_table.cellWidget(row, 5)
            subtotal_widget = self.product_table.cellWidget(row, 6)
            if ref_widget is not None:
                self._set_line_edit_text(ref_widget, str(product["ref_b_analyse"] or 0))
            if num_act_widget is not None:
                self._set_line_edit_text(num_act_widget, self.selected_num_acts.get(pid) or "")
        else:
            physico_widget = self.product_table.cellWidget(row, 1)
            toxico_widget = self.product_table.cellWidget(row, 2)
            micro_widget = self.product_table.cellWidget(row, 3)
            subtotal_widget = self.product_table.cellWidget(row, 4)

        self._set_line_edit_text(physico_widget, self.format_number(product["physico"]))
        self._set_line_edit_text(toxico_widget, self.format_number(product["toxico"]))
        self._set_line_edit_text(micro_widget, self.format_number(product["micro"]))
        self._set_line_edit_text(subtotal_widget, self.format_number(product["subtotal"]))

    def _persist_row_changes(self, row, pid):
        if self.invoice_type == "standard":
            physico_col = 3
            toxico_col = 4
            micro_col = 5
            subtotal_col = 6
            num_act_widget = self.product_table.cellWidget(row, 2)
            num_act = self._normalize_num_act(num_act_widget.text() if num_act_widget else "")
            if self.selected_products.get(pid, False):
                self.selected_num_acts[pid] = num_act
            ref = int(self.parse_number(self.product_table.cellWidget(row, 1).text()))
        else:
            physico_col = 1
            toxico_col = 2
            micro_col = 3
            subtotal_col = 4
            ref = 0

        physico_widget = self.product_table.cellWidget(row, physico_col)
        toxico_widget = self.product_table.cellWidget(row, toxico_col)
        micro_widget = self.product_table.cellWidget(row, micro_col)
        subtotal_widget = self.product_table.cellWidget(row, subtotal_col)

        physico = int(self.parse_number(physico_widget.text() if physico_widget else 0))
        toxico = int(self.parse_number(toxico_widget.text() if toxico_widget else 0))
        micro = int(self.parse_number(micro_widget.text() if micro_widget else 0))
        subtotal = int(self.parse_number(subtotal_widget.text() if subtotal_widget else 0))

        self.product_service.update_product(
            pid,
            ref,
            None,
            physico,
            toxico,
            micro,
            subtotal,
            update_ref=False,
        )
        self.catalog_signature = self._safe_catalog_signature()

    def get_product_subtotal(self, product_id):
        row = self._find_row_for_product(product_id)
        if row < 0:
            return None

        subtotal_col = 6 if self.invoice_type == "standard" else 4
        subtotal_widget = self.product_table.cellWidget(row, subtotal_col)
        if subtotal_widget is None:
            return None
        return self.parse_number(subtotal_widget.text())

    def _begin_designation_edit(self, row):
        if self.product_table.cellWidget(row, 0) is not None:
            return
        item = self.product_table.item(row, 0)
        if item is None:
            return
        designation_edit = QLineEdit(item.text())
        if self.selected_products.get(item.data(Qt.UserRole), False):
            designation_edit.setProperty("selectedRow", True)
            designation_edit.style().unpolish(designation_edit)
            designation_edit.style().polish(designation_edit)
        self.product_table.setCellWidget(row, 0, designation_edit)
        designation_edit.selectAll()
        designation_edit.setFocus()

    def _save_designation_edit(self, row, pid):
        designation_edit = self.product_table.cellWidget(row, 0)
        if designation_edit is None:
            return True

        new_name = designation_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Désignation invalide", "La désignation du produit ne peut pas être vide.")
            designation_edit.setFocus()
            return False

        item = self.product_table.item(row, 0)
        if item is None:
            return False

        if new_name != item.text().strip():
            self.product_table.removeCellWidget(row, 0)
            item.setText(new_name)
            self.product_service.update_product_name(pid, new_name)
            self.catalog_signature = self._safe_catalog_signature()
            return True

        self.product_table.removeCellWidget(row, 0)
        return True

    def format_number(self, value):
        v = self.parse_number(value)
        formatted = f"{int(v):,}".replace(",", " ")
        return f"{formatted} Ar"

    def parse_number(self, value):
        try:
            if value is None:
                return 0.0
            cleaned = str(value).replace("\u00a0", " ").replace("Ariary", "").replace("Ar", "").replace(" ", "").strip()
            if cleaned == "":
                return 0.0
            return float(cleaned)
        except (TypeError, ValueError):
            return 0.0

    def _display_num_act(self, value):
        if value is None:
            return ""
        text = str(value).strip()
        if text.lower() == "none":
            return ""
        return text

    def _normalize_num_act(self, value):
        text = str(value or "").strip()
        return text or None

    def validate_num_act_row(self, row):
        if self.invoice_type != "standard":
            return True
        num_act_widget = self.product_table.cellWidget(row, 2)
        if num_act_widget is None:
            return True

        num_act = self._normalize_num_act(num_act_widget.text())
        self._set_line_edit_text(num_act_widget, num_act or "")
        return True

    def set_loaded_record_locked(self, locked):
        self.loaded_record_locked = bool(locked)
        self.add_product_btn.setEnabled(self.can_manage_catalog and not self.loaded_record_locked)
        for row in range(self.product_table.rowCount()):
            self._update_row_action_state(row)

    def _update_row_action_state(self, row):
        if self.invoice_type == "standard":
            btn_del_col = 7
            btn_mod_col = 8
            btn_sel_col = 9
        else:
            btn_del_col = 5
            btn_mod_col = 6
            btn_sel_col = 7
        btn_del = self.product_table.cellWidget(row, btn_del_col)
        btn_mod = self.product_table.cellWidget(row, btn_mod_col)
        btn_sel = self.product_table.cellWidget(row, btn_sel_col)
        if btn_del:
            btn_del.setEnabled(self.can_manage_catalog and not self.loaded_record_locked)
        if btn_mod:
            btn_mod.setEnabled(self.can_manage_catalog)
        if btn_sel:
            btn_sel.setEnabled(not self.loaded_record_locked)

    def delete_product_row(self, pid, row):
        if not self.can_manage_catalog:
            return
        if self.loaded_record_locked:
            return
        if self.product_service.db.product_is_used_in_records(pid):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Suppression impossible",
                "Ce produit ne peut pas être supprimé car il est déjà utilisé dans des enregistrements."
            )
            return
        current_type_id = self.type_list.currentItem().data(Qt.UserRole) if self.type_list.currentItem() else None
        self.product_service.delete_product(pid)
        self._after_local_catalog_change(selected_type_id=current_type_id)

    def on_price_component_changed(self, row):
        item = self.product_table.item(row, 0)
        if item is None:
            return

        if self.invoice_type == "standard":
            physico_col = 3
            toxico_col = 4
            micro_col = 5
            subtotal_col = 6
        else:  # proforma
            physico_col = 1
            toxico_col = 2
            micro_col = 3
            subtotal_col = 4

        physico_widget = self.product_table.cellWidget(row, physico_col)
        toxico_widget = self.product_table.cellWidget(row, toxico_col)
        micro_widget = self.product_table.cellWidget(row, micro_col)
        subtotal_widget = self.product_table.cellWidget(row, subtotal_col)

        physico = self.parse_number(physico_widget.text())
        toxico = self.parse_number(toxico_widget.text())
        micro = self.parse_number(micro_widget.text())

        subtotal_value = physico + toxico + micro
        subtotal_text = self.format_number(subtotal_value)

        self._set_line_edit_text(subtotal_widget, subtotal_text)

        pid = item.data(Qt.UserRole)
        if self.invoice_type == "standard":
            num_act = self._normalize_num_act(self.product_table.cellWidget(row, 2).text())
            if self.selected_products.get(pid, False):
                self.selected_num_acts[pid] = num_act

        if self.selected_products.get(pid, False):
            self.selection_changed.emit()

    def toggle_select(self, pid, row):
        if self.loaded_record_locked:
            return
        btn_col = 9 if self.invoice_type == "standard" else 7
        btn = self.product_table.cellWidget(row, btn_col)
        currently_selected = bool(self.selected_products.get(pid, False))

        if not currently_selected:
            # Select: mark and append to order
            if btn:
                btn.setText("Annuler")
            self.selected_products[pid] = True
            if pid not in self.selection_order:
                self.selection_order.append(pid)
            if self.invoice_type == "standard":
                num_act_widget = self.product_table.cellWidget(row, 2)
                current_num_act = self._normalize_num_act(num_act_widget.text() if num_act_widget else "")
                self.selected_num_acts[pid] = current_num_act
            self.apply_selection_style(row)
        else:
            # Deselect: unmark and remove from order
            if btn:
                btn.setText("Choisir")
            self.selected_products[pid] = False
            if pid in self.selection_order:
                self.selection_order.remove(pid)
            if pid in self.selected_refs:
                del self.selected_refs[pid]
            if pid in self.selected_num_acts:
                del self.selected_num_acts[pid]
            self.clear_selection_style(row)

        # Refresh displayed refs for standard rows according to selected_refs mapping
        self._refresh_preview_refs()
        self.selection_changed.emit()

    def _refresh_preview_refs(self):
        if self.invoice_type != "standard":
            return

        persisted_refs = {}
        for pid in self.selection_order:
            if pid in self.selected_products and self.selected_products[pid] and pid in self.selected_refs:
                persisted_refs[pid] = self.selected_refs[pid]

        preview_refs = dict(persisted_refs)
        try:
            next_ref = int(self.product_service.get_max_ref_b_analyse() or 0) + 1
        except Exception:
            next_ref = 1

        for pid in self.selection_order:
            if not self.selected_products.get(pid, False):
                continue
            if pid in preview_refs:
                continue
            preview_refs[pid] = next_ref
            next_ref += 1

        self._renumber_selection_ui(preview_refs)

    def _renumber_selection_ui(self, ref_mapping=None):
        # Keep UI in sync with the provided/persisted ref mapping.
        ref_mapping = ref_mapping if ref_mapping is not None else self.selected_refs
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
                if pid in ref_mapping:
                    ref_widget.setText(str(ref_mapping[pid]))
                else:
                    ref_widget.setText("0")

    def apply_selection_style(self, row):
        for col in range(self.product_table.columnCount()):
            item = self.product_table.item(row, col)
            if item:
                item.setBackground(QColor("#2F5A8F"))
                item.setForeground(QColor("white"))
        if self.invoice_type == "standard":
            editable_cols = [1, 2, 3, 4, 5]
        else:
            editable_cols = [1, 2, 3]
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
                item.setForeground(QColor("black"))
        if self.invoice_type == "standard":
            editable_cols = [1, 2, 3, 4, 5]
        else:
            editable_cols = [1, 2, 3]
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

    def select_products(self, product_ids, ref_mapping=None, num_act_mapping=None):
        # Select given products and maintain selection order.
        # For standard invoices, ref_mapping can restore previously saved refs.
        ref_mapping = ref_mapping or {}
        num_act_mapping = num_act_mapping or {}
        for pid in product_ids:
            already_selected = self.selected_products.get(pid, False)
            if not already_selected:
                self.selected_products[pid] = True
                if pid not in self.selection_order:
                    self.selection_order.append(pid)
            if self.invoice_type == "standard":
                existing_ref = ref_mapping.get(pid)
                if existing_ref is not None:
                    self.selected_refs[pid] = int(existing_ref)
                self.selected_num_acts[pid] = self._normalize_num_act(num_act_mapping.get(pid))
            # Trouver la ligne et appliquer la sélection UI
            for row in range(self.product_table.rowCount()):
                row_item = self.product_table.item(row, 0)
                if not row_item:
                    continue
                item_pid = row_item.data(Qt.UserRole)
                if item_pid == pid:
                    if self.invoice_type == "standard":
                        num_act_widget = self.product_table.cellWidget(row, 2)
                        if num_act_widget is not None:
                            num_act_widget.setText(self.selected_num_acts.get(pid) or "")
                    btn_col = 9 if self.invoice_type == "standard" else 7
                    btn = self.product_table.cellWidget(row, btn_col)
                    if btn:
                        btn.setText("Annuler")
                        self.apply_selection_style(row)
                    break
        # Refresh refs in UI after bulk selection
        self._refresh_preview_refs()
        # la sélection ne désactive plus les champs du formulaire client
        return

    def load_products(self):
        self.product_table.setRowCount(0)
        if not self.type_list.currentItem():
            self.selection_changed.emit()
            return
        tid = self.type_list.currentItem().data(Qt.UserRole)
        if tid is None:
            self.selection_changed.emit()
            return
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
                num_act = ""
                physico = product['physico']
                toxico = product['toxico']
                micro = product['micro']
                subtotal = product['subtotal']
                self.add_product_row(pid, name, ref, num_act, physico, toxico, micro, subtotal)
        for row in range(self.product_table.rowCount()):
            self._update_row_action_state(row)
        self.selection_changed.emit()

    def _safe_catalog_signature(self):
        try:
            return self.product_service.db.get_catalog_signature()
        except Exception:
            return None

    def refresh_catalog_silently(self):
        if not self.isVisible():
            return

        latest_signature = self._safe_catalog_signature()
        if latest_signature is None:
            return
        if self.catalog_signature is None:
            self.catalog_signature = latest_signature
            return
        if latest_signature == self.catalog_signature:
            return

        if self._is_edit_active():
            self._mark_catalog_reload_pending(latest_signature=latest_signature)
            return

        self.catalog_signature = latest_signature
        self._reload_catalog_preserving_state()
        self._show_catalog_notification("Le catalogue a ete mis a jour automatiquement.")

    def _after_local_catalog_change(self, selected_type_id=None):
        if self._is_edit_active():
            self._mark_catalog_reload_pending()
            return
        self._reload_catalog_preserving_state(selected_type_id=selected_type_id)
        self.catalog_signature = self._safe_catalog_signature()

    def _reload_catalog_preserving_state(self, selected_type_id=None):
        if self._is_edit_active():
            self._mark_catalog_reload_pending()
            return

        current_type_id = selected_type_id
        if current_type_id is None:
            current_item = self.type_list.currentItem()
            if current_item is not None:
                current_type_id = current_item.data(Qt.UserRole)

        has_selection = self.load_types(selected_type_id=current_type_id)
        if has_selection:
            self.load_products()
        else:
            self.product_table.setRowCount(0)
            self.selection_changed.emit()

    def _show_catalog_notification(self, message):
        self.catalog_notification.setText(message)
        self.catalog_notification.setVisible(True)
        self.catalog_notice_timer.start(4000)

    def _cancel_edit_if_active(self, row):
        """If a row is in edit mode (widgets not-readonly), cancel it cleanly."""
        if self.invoice_type == "standard":
            widget_col, btn_mod_col = 2, 8
            editable_cols, amount_cols = [1, 2, 3, 4, 5], [3, 4, 5]
        else:
            widget_col, btn_mod_col = 1, 6
            editable_cols, amount_cols = [1, 2, 3], [1, 2, 3]
        widget = self.product_table.cellWidget(row, widget_col)
        if widget is None or widget.isReadOnly():
            return  # Not in edit mode
        btn_mod = self.product_table.cellWidget(row, btn_mod_col)
        if btn_mod:
            btn_mod.setText("Modifier")
        designation_item = self.product_table.item(row, 0)
        pid = designation_item.data(Qt.UserRole) if designation_item is not None else None
        if self.product_table.cellWidget(row, 0) is not None:
            self.product_table.removeCellWidget(row, 0)
        if pid is not None:
            self._restore_row_from_database(row, pid)
        else:
            for col in amount_cols:
                w = self.product_table.cellWidget(row, col)
                if w:
                    self._set_line_edit_text(w, self.format_number(w.text()))
        for col in editable_cols:
            w = self.product_table.cellWidget(row, col)
            if w:
                w.setReadOnly(True)
        if self.active_edit_row == row:
            self.active_edit_row = None

    def clear_selection(self):
        self.set_loaded_record_locked(False)
        # Annuler tout édit en cours avant de changer d'état
        for row in range(self.product_table.rowCount()):
            self._cancel_edit_if_active(row)
        self._flush_pending_catalog_reload()
        # Réinitialiser l'état mémoire même si certaines lignes ne sont pas visibles
        self.selected_products.clear()
        self.selection_order.clear()
        self.selected_refs.clear()
        self.selected_num_acts.clear()

        # Nettoyer l'UI des lignes visibles
        for row in range(self.product_table.rowCount()):
            btn_col = 9 if self.invoice_type == "standard" else 7
            btn = self.product_table.cellWidget(row, btn_col)
            if btn:
                btn.setText("Choisir")
            self.clear_selection_style(row)
            if self.invoice_type == "standard":
                num_act_widget = self.product_table.cellWidget(row, 2)
                if num_act_widget:
                    num_act_widget.setText("")
        self.enable_form_fields()
        # Renumber UI refs to reflect cleared selections
        self._refresh_preview_refs()
        self.selection_changed.emit()

    def get_selected_ref_mapping(self):
        if self.invoice_type != "standard":
            return {}
        selected_set = {pid for pid, selected in self.selected_products.items() if selected}
        return {pid: ref for pid, ref in self.selected_refs.items() if pid in selected_set}

    def get_selected_num_act_mapping(self):
        if self.invoice_type != "standard":
            return {}
        selected_set = {pid for pid, selected in self.selected_products.items() if selected}

        for row in range(self.product_table.rowCount()):
            item = self.product_table.item(row, 0)
            if not item:
                continue
            pid = item.data(Qt.UserRole)
            if pid not in selected_set:
                continue
            num_act_widget = self.product_table.cellWidget(row, 2)
            if num_act_widget is None:
                continue
            self.selected_num_acts[pid] = self._normalize_num_act(num_act_widget.text())

        return {pid: self._normalize_num_act(num_act) for pid, num_act in self.selected_num_acts.items() if pid in selected_set}

    def _apply_stylesheet(self, stylesheet_path):
        try:
            with open(resolve_resource_path(stylesheet_path), "r", encoding="utf-8") as file:
                self.setStyleSheet(file.read())
        except FileNotFoundError:
            print(f"Stylesheet {stylesheet_path} not found.")

    def cleanup(self):
        if self.catalog_refresh_timer is not None:
            self.catalog_refresh_timer.stop()
        self.catalog_notice_timer.stop()

