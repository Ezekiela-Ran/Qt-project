from PySide6.QtWidgets import (
    QListWidgetItem, QTableWidgetItem, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QTableWidget, QAbstractItemView, QLineEdit, QLabel, QInputDialog, QMessageBox,
)
from PySide6.QtGui import QIntValidator, QColor
from PySide6.QtCore import Qt, Signal, QTimer, QSignalBlocker, QDate
from PySide6.QtWidgets import QHeaderView
import re
from utils.path_utils import resolve_resource_path
from views.foundation.globals import GlobalVariable


CATALOG_REFRESH_INTERVAL_MS = 5000


class ProductManager(QWidget):
    selection_changed = Signal()  # Signal émis quand la sélection change

    STANDARD_COLUMNS = {
        "designation": 0,
        "quantity": 1,
        "duration": 2,
        "ref": 3,
        "num_act": 4,
        "physico": 5,
        "toxico": 6,
        "micro": 7,
        "subtotal": 8,
        "delete": 9,
        "edit": 10,
        "select": 11,
    }
    PROFORMA_COLUMNS = {
        "designation": 0,
        "quantity": 1,
        "physico": 2,
        "toxico": 3,
        "micro": 4,
        "subtotal": 5,
        "delete": 6,
        "edit": 7,
        "select": 8,
    }
    
    def __init__(self, product_service, invoice_type="standard"):
        super().__init__()
        
        self.product_service = product_service
        self.invoice_type = invoice_type
        self.selected_products = {}  # dictionnaire {pid: True/False}
        self.selection_order = []  # ordre de sélection pour numéroter dynamiquement
        self.selected_refs = {}  # dictionnaire {pid: [ref_b_analyse, ...]} pour standard
        self.selected_num_acts = {}  # dictionnaire {pid: texte ou liste de num_act} pour standard
        self.selected_result_dates = {}  # dictionnaire {pid: yyyy-MM-dd} pour standard
        self.selected_quantities = {}
        self.product_default_quantities = {}
        self.product_analysis_durations = {}
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
        self.catalog_notification.setMinimumHeight(34)
        self.catalog_notification.setWordWrap(True)
        self.catalog_notification.setAlignment(Qt.AlignCenter)
        self._clear_catalog_notification()
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
            self.product_table.setColumnCount(9)
            self.product_table.setHorizontalHeaderLabels(["Désignation", "Nombre", "Physico", "Toxico", "Micro", "Sous-total", "Suppr", "Modif", "Choisir"])
        else:
            self.product_table.setColumnCount(12)
            self.product_table.setHorizontalHeaderLabels(["Désignation", "Nombre", "Durée", "Ref.b.analyse", "N° Acte", "Physico", "Toxico", "Micro", "Sous-total", "Suppr", "Modif", "Choisir"])
        self.product_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # Hide the reference column from the user but keep the widget so we can update it
        if self.invoice_type == "standard":
            self.product_table.setColumnHidden(self._col("ref"), True)
        self._configure_product_table_columns()

        add_button_layout = QHBoxLayout()
        add_button_layout.addStretch()
        add_button_layout.addWidget(self.add_product_btn)
        product_list_layout.addLayout(add_button_layout)
        product_list_layout.addWidget(self.product_table)

        self._apply_stylesheet("styles/product_manager.qss")
        self.catalog_notice_timer = QTimer(self)
        self.catalog_notice_timer.setSingleShot(True)
        self.catalog_notice_timer.timeout.connect(self._clear_catalog_notification)
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
        self.add_type_btn.setVisible(self._can_manage_types())
        self.edit_type_btn.setVisible(self._can_manage_types())
        self.del_type_btn.setVisible(self._can_manage_types())
        self.add_product_btn.setVisible(self._can_manage_product_catalog())
        self.product_table.setColumnHidden(self._col("delete"), not self._can_manage_product_catalog())
        self.product_table.setColumnHidden(self._col("edit"), not self._can_use_row_edit())

    def _col(self, name):
        if self.invoice_type == "standard":
            return self.STANDARD_COLUMNS[name]
        return self.PROFORMA_COLUMNS[name]

    def _has_duration_column(self):
        return self.invoice_type == "standard"

    def _catalog_management_locked(self):
        return self.invoice_type == "proforma"

    def _can_manage_types(self):
        return self.can_manage_catalog and not self._catalog_management_locked()

    def _can_manage_product_catalog(self):
        return self.can_manage_catalog and not self._catalog_management_locked()

    def _can_use_row_edit(self):
        return self.can_manage_catalog or self.invoice_type == "proforma"

    def _is_quantity_only_row_edit(self):
        return self.invoice_type == "proforma" and not self.can_manage_catalog

    def _editable_row_columns(self):
        if self.invoice_type == "standard":
            return [self._col("quantity"), self._col("duration"), self._col("ref"), self._col("num_act"), self._col("physico"), self._col("toxico"), self._col("micro")]
        if self._is_quantity_only_row_edit():
            return [self._col("quantity")]
        return [self._col("quantity"), self._col("physico"), self._col("toxico"), self._col("micro")]

    def _configure_product_table_columns(self):
        header = self.product_table.horizontalHeader()
        header.setSectionResizeMode(self._col("designation"), QHeaderView.Interactive)
        compact_columns = ["quantity", "physico", "toxico", "micro", "subtotal"]
        if self._has_duration_column():
            compact_columns.insert(1, "duration")
        if self.invoice_type == "standard":
            compact_columns.insert(3, "num_act")
        for column_name in compact_columns:
            header.setSectionResizeMode(self._col(column_name), QHeaderView.Interactive)
        self.product_table.setColumnWidth(self._col("designation"), 220)
        self.product_table.setColumnWidth(self._col("quantity"), 58)
        if self._has_duration_column():
            self.product_table.setColumnWidth(self._col("duration"), 58)
        if self.invoice_type == "standard":
            self.product_table.setColumnWidth(self._col("num_act"), 110)
        self.product_table.setColumnWidth(self._col("physico"), 76)
        self.product_table.setColumnWidth(self._col("toxico"), 76)
        self.product_table.setColumnWidth(self._col("micro"), 76)
        self.product_table.setColumnWidth(self._col("subtotal"), 88)
        header.setSectionResizeMode(self._col("delete"), QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self._col("edit"), QHeaderView.ResizeToContents)
        header.setSectionResizeMode(self._col("select"), QHeaderView.ResizeToContents)
    
    def load_types(self, selected_type_id=None):
        if selected_type_id is None and self.type_list.currentItem():
            selected_type_id = self.type_list.currentItem().data(Qt.UserRole)

        self.type_list.blockSignals(True)
        self.type_list.clear()
        types = self.product_service.get_all_product_types()
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
        if not self._can_manage_types():
            return
        name, ok = QInputDialog.getText(self, "Nouveau Type", "Nom du type:")
        if ok and name:
            new_type_id = self.product_service.insert_type(name)
            self._after_local_catalog_change(selected_type_id=new_type_id)

    def edit_type(self):
        if not self._can_manage_types():
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
        if not self._can_manage_types():
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
        if not self._can_manage_product_catalog():
            return
        if self.loaded_record_locked:
            return
        if not self.type_list.currentItem():
            return
        tid = self.type_list.currentItem().data(Qt.UserRole)
        name, ok = QInputDialog.getText(self, "Nouveau Produit", "Nom du produit:")
        if not ok:
            return
        name = (name or "").strip()
        if not name:
            return
        analysis_duration_days, duration_ok = QInputDialog.getInt(
            self,
            "Nouveau Produit",
            "Durée d'analyse (jours):",
            value=0,
            minValue=0,
            maxValue=3650,
        )
        if duration_ok:
            self.product_service.add_product(tid, name, analysis_duration_days, 1)
            self._after_local_catalog_change(selected_type_id=tid)

    @staticmethod
    def _compute_result_date_from_duration(duration_days):
        try:
            duration_value = max(int(duration_days or 0), 0)
        except (TypeError, ValueError):
            duration_value = 0
        return QDate.currentDate().addDays(duration_value).toString("yyyy-MM-dd")

    def _parse_positive_int(self, value, default=0, minimum=0):
        try:
            return max(int(str(value or "").strip() or default), minimum)
        except (TypeError, ValueError):
            return max(int(default), minimum)

    @staticmethod
    def _normalize_designation_key(value):
        return " ".join(str(value or "").split()).strip().casefold()

    def _designation_key_for_pid(self, pid):
        row = self._find_row_for_product(pid)
        if row >= 0:
            item = self.product_table.item(row, self._col("designation"))
            if item is not None:
                return self._normalize_designation_key(item.text())

        product = self.product_service.get_product_by_id(pid)
        if not product:
            return ""
        return self._normalize_designation_key(product.get("product_name"))

    def _split_series_values(self, value):
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item or "").strip()]
        return [chunk.strip() for chunk in re.split(r"[;,\n]+", str(value or "")) if chunk.strip()]

    def _normalize_num_act_series(self, value, quantity):
        values = [self._normalize_num_act(chunk) for chunk in self._split_series_values(value)]
        values = [item for item in values if item]
        normalized = values[:quantity]
        if len(normalized) == 1 and quantity > 1:
            normalized = normalized * quantity
        while len(normalized) < quantity:
            normalized.append(None)
        return normalized

    def _format_num_act_series(self, values):
        if isinstance(values, list):
            compact_values = [str(value).strip() for value in values if str(value or "").strip()]
            if not compact_values:
                return ""
            if len(set(compact_values)) == 1:
                return compact_values[0]
            return "; ".join(compact_values)
        return self._display_num_act(values)

    def _format_ref_preview(self, refs):
        if not isinstance(refs, list):
            refs = [refs] if refs is not None else []
        refs = [int(ref_value) for ref_value in refs if ref_value is not None]
        if not refs:
            return "0"
        if len(refs) == 1:
            return str(refs[0])
        return f"{refs[0]}-{refs[-1]}"

    @staticmethod
    def _default_ref_preview():
        return "0"

    def add_product_row(self, pid, name, default_quantity, duration_days, ref, num_act, physico, toxico, micro, subtotal):
        row = self.product_table.rowCount()
        self.product_table.insertRow(row)

        self.product_table.setItem(row, 0, QTableWidgetItem(name))
        self.product_table.item(row, 0).setData(Qt.UserRole, pid)

        int_validator = QIntValidator(0, 999999)
        quantity_edit = QLineEdit(str(self._parse_positive_int(default_quantity, default=1, minimum=1))); quantity_edit.setReadOnly(True)
        quantity_edit.setValidator(QIntValidator(1, 999))
        self.product_table.setCellWidget(row, self._col("quantity"), quantity_edit)

        if self.invoice_type == "standard":
            duration_edit = QLineEdit(str(self._parse_positive_int(duration_days, default=0, minimum=0))); duration_edit.setReadOnly(True)
            duration_edit.setValidator(int_validator)
            self.product_table.setCellWidget(row, self._col("duration"), duration_edit)
            ref_edit = QLineEdit(str(ref)); ref_edit.setReadOnly(True)
            self.product_table.setCellWidget(row, self._col("ref"), ref_edit)
            num_act_edit = QLineEdit(self._display_num_act(num_act)); num_act_edit.setReadOnly(True)
            physico_edit = QLineEdit(self.format_number(physico)); physico_edit.setReadOnly(True)
            toxico_edit = QLineEdit(self.format_number(toxico)); toxico_edit.setReadOnly(True)
            micro_edit = QLineEdit(self.format_number(micro)); micro_edit.setReadOnly(True)
            subtotal_edit = QLineEdit(self.format_number(self._compute_display_subtotal(subtotal, default_quantity))); subtotal_edit.setReadOnly(True)

            # Set validators for integer fields
            physico_edit.setValidator(int_validator)
            toxico_edit.setValidator(int_validator)
            micro_edit.setValidator(int_validator)
            ref_edit.setValidator(int_validator)
            subtotal_edit.setValidator(int_validator)

            self.product_table.setCellWidget(row, self._col("num_act"), num_act_edit)
            self.product_table.setCellWidget(row, self._col("physico"), physico_edit)
            self.product_table.setCellWidget(row, self._col("toxico"), toxico_edit)
            self.product_table.setCellWidget(row, self._col("micro"), micro_edit)
            self.product_table.setCellWidget(row, self._col("subtotal"), subtotal_edit)
        else:  # proforma
            physico_edit = QLineEdit(self.format_number(physico)); physico_edit.setReadOnly(True)
            toxico_edit = QLineEdit(self.format_number(toxico)); toxico_edit.setReadOnly(True)
            micro_edit = QLineEdit(self.format_number(micro)); micro_edit.setReadOnly(True)
            subtotal_edit = QLineEdit(self.format_number(self._compute_display_subtotal(subtotal, default_quantity))); subtotal_edit.setReadOnly(True)

            # Set validators for integer fields
            physico_edit.setValidator(int_validator)
            toxico_edit.setValidator(int_validator)
            micro_edit.setValidator(int_validator)
            subtotal_edit.setValidator(int_validator)

            self.product_table.setCellWidget(row, self._col("physico"), physico_edit)
            self.product_table.setCellWidget(row, self._col("toxico"), toxico_edit)
            self.product_table.setCellWidget(row, self._col("micro"), micro_edit)
            self.product_table.setCellWidget(row, self._col("subtotal"), subtotal_edit)

        # Connect automatic recalculation et mise à jour DB sur modification des champs relevant du calcul.
        quantity_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))
        physico_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))
        toxico_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))
        micro_edit.textChanged.connect(lambda _: self.on_price_component_changed(row))

        btn_del = QPushButton("Suppr")
        btn_mod = QPushButton("Modifier")
        btn_sel = QPushButton("Choisir")
        btn_del.setObjectName("rowActionButton")
        btn_mod.setObjectName("rowActionButton")
        btn_sel.setObjectName("rowActionButton")

        self.product_table.setCellWidget(row, self._col("delete"), btn_del)
        self.product_table.setCellWidget(row, self._col("edit"), btn_mod)
        self.product_table.setCellWidget(row, self._col("select"), btn_sel)

        btn_del.clicked.connect(lambda: self.delete_product_row(pid, row))
        btn_mod.clicked.connect(self.toggle_edit_from_sender)
        btn_sel.clicked.connect(lambda: self.toggle_select(pid, row))

        if not self.can_manage_catalog:
            btn_del.setVisible(False)
            btn_mod.setVisible(self._can_use_row_edit())

        btn_del.setEnabled(self.can_manage_catalog and not self.loaded_record_locked)
        btn_mod.setEnabled(self._can_use_row_edit())
        btn_sel.setEnabled(not self.loaded_record_locked)

        # Réappliquer style si déjà sélectionné
        if pid in self.selected_products and self.selected_products[pid]:
            btn_sel.setText("Annuler")
            if self.invoice_type == "standard":
                selected_num_act = self.selected_num_acts.get(pid)
                if selected_num_act is not None:
                    num_act_edit.setText(self._format_num_act_series(selected_num_act))
            selected_quantity = self.selected_quantities.get(pid)
            if selected_quantity is not None:
                quantity_edit.setText(str(selected_quantity))
                self._set_row_subtotal_display(row, subtotal)
            self.apply_selection_style(row)

    def toggle_edit(self, row):
        if not self._can_use_row_edit():
            return False
        if self.active_edit_row is not None and self.active_edit_row != row:
            return False
        designation_item = self.product_table.item(row, 0)
        if designation_item is None:
            return False
        pid = designation_item.data(Qt.UserRole)
        if pid is None:
            return False
        if self.invoice_type == "standard":
            widget_col = self._col("num_act")
            btn_col = self._col("edit")
            amount_cols = [self._col("physico"), self._col("toxico"), self._col("micro")]
            focus_col = self._col("quantity")
        else:
            widget_col = self._col("quantity")
            btn_col = self._col("edit")
            amount_cols = [self._col("physico"), self._col("toxico"), self._col("micro")]
            focus_col = self._col("quantity")
        editable_cols = self._editable_row_columns()
        widget = self.product_table.cellWidget(row, widget_col)
        btn = self.product_table.cellWidget(row, btn_col)
        if widget.isReadOnly():
            self.active_edit_row = row
            btn.setText("Sauver")
            if not self._is_quantity_only_row_edit():
                self._begin_designation_edit(row)
                for col in amount_cols:
                    amount_widget = self.product_table.cellWidget(row, col)
                    if amount_widget:
                        self._set_line_edit_text(amount_widget, str(int(self.parse_number(amount_widget.text()))))
            for col in editable_cols:
                self.product_table.cellWidget(row, col).setReadOnly(False)
            self.product_table.cellWidget(row, focus_col).setFocus()
            return True
        return self.commit_active_edit()

    def commit_active_edit(self):
        row = self.active_edit_row
        if row is None:
            return True

        designation_item = self.product_table.item(row, 0)
        if designation_item is None:
            self.active_edit_row = None
            return True

        pid = designation_item.data(Qt.UserRole)
        if pid is None:
            self.active_edit_row = None
            return True

        editable_cols = self._editable_row_columns()
        amount_cols = [self._col("physico"), self._col("toxico"), self._col("micro")]
        btn = self.product_table.cellWidget(row, self._col("edit"))

        if self.invoice_type == "standard" and self._should_auto_select_standard_row(row, pid):
            self._select_row_for_invoice(pid, row)
            self._refresh_preview_refs()

        if self.invoice_type == "standard" and not self.validate_num_act_row(row):
            self.product_table.cellWidget(row, self._col("num_act")).setFocus()
            return False
        if not self._save_designation_edit(row, pid):
            return False

        self.on_price_component_changed(row)
        self._persist_row_changes(row, pid)

        if btn:
            btn.setText("Modifier")
        if not self._is_quantity_only_row_edit():
            for col in amount_cols:
                amount_widget = self.product_table.cellWidget(row, col)
                if amount_widget:
                    self._set_line_edit_text(amount_widget, self.format_number(amount_widget.text()))
        for col in editable_cols:
            widget = self.product_table.cellWidget(row, col)
            if widget:
                widget.setReadOnly(True)
        self.active_edit_row = None
        if self.selected_products.get(pid, False):
            self.selection_changed.emit()
        self._flush_pending_catalog_reload()
        return True

    def toggle_edit_from_sender(self):
        if not self._can_use_row_edit():
            return
        button = self.sender()
        if button is None:
            return
        btn_col = self._col("edit")
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
        self._show_catalog_notification("Le catalogue a été mis à jour automatiquement.")

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
            quantity_widget = self.product_table.cellWidget(row, self._col("quantity"))
            duration_widget = self.product_table.cellWidget(row, self._col("duration"))
            ref_widget = self.product_table.cellWidget(row, self._col("ref"))
            num_act_widget = self.product_table.cellWidget(row, self._col("num_act"))
            physico_widget = self.product_table.cellWidget(row, self._col("physico"))
            toxico_widget = self.product_table.cellWidget(row, self._col("toxico"))
            micro_widget = self.product_table.cellWidget(row, self._col("micro"))
            subtotal_widget = self.product_table.cellWidget(row, self._col("subtotal"))
            if quantity_widget is not None:
                current_quantity = self.selected_quantities.get(pid, 1)
                self._set_line_edit_text(quantity_widget, str(self._parse_positive_int(current_quantity, default=1, minimum=1)))
            if duration_widget is not None:
                self._set_line_edit_text(duration_widget, str(self._parse_positive_int(product.get("analysis_duration_days"), default=0, minimum=0)))
            if ref_widget is not None:
                ref_value = self._format_ref_preview(self.selected_refs.get(pid)) if self.selected_products.get(pid, False) else self._default_ref_preview()
                self._set_line_edit_text(ref_widget, ref_value)
            if num_act_widget is not None:
                num_act_value = self.selected_num_acts.get(pid) if self.selected_products.get(pid, False) else ""
                self._set_line_edit_text(num_act_widget, self._format_num_act_series(num_act_value))
        else:
            quantity_widget = self.product_table.cellWidget(row, self._col("quantity"))
            physico_widget = self.product_table.cellWidget(row, self._col("physico"))
            toxico_widget = self.product_table.cellWidget(row, self._col("toxico"))
            micro_widget = self.product_table.cellWidget(row, self._col("micro"))
            subtotal_widget = self.product_table.cellWidget(row, self._col("subtotal"))
            if quantity_widget is not None:
                current_quantity = self.selected_quantities.get(pid, 1)
                self._set_line_edit_text(quantity_widget, str(self._parse_positive_int(current_quantity, default=1, minimum=1)))

        self._set_line_edit_text(physico_widget, self.format_number(product["physico"]))
        self._set_line_edit_text(toxico_widget, self.format_number(product["toxico"]))
        self._set_line_edit_text(micro_widget, self.format_number(product["micro"]))
        self._set_row_subtotal_display(row, product["subtotal"])

    def _persist_row_changes(self, row, pid):
        if self.invoice_type == "standard":
            physico_col = self._col("physico")
            toxico_col = self._col("toxico")
            micro_col = self._col("micro")
            subtotal_col = self._col("subtotal")
            quantity_widget = self.product_table.cellWidget(row, self._col("quantity"))
            duration_widget = self.product_table.cellWidget(row, self._col("duration"))
            num_act_widget = self.product_table.cellWidget(row, self._col("num_act"))
            quantity_value = self._parse_positive_int(quantity_widget.text() if quantity_widget else 1, default=1, minimum=1)
            analysis_duration_days = self._parse_positive_int(duration_widget.text() if duration_widget else self.product_analysis_durations.get(pid, 0), default=0, minimum=0)
            num_act = str(num_act_widget.text() if num_act_widget else "").strip()
            if self.selected_products.get(pid, False):
                self.selected_num_acts[pid] = num_act
                self.selected_quantities[pid] = quantity_value
                self.selected_result_dates[pid] = self._compute_result_date_from_duration(analysis_duration_days)
            ref = int(self.parse_number(self.product_table.cellWidget(row, self._col("ref")).text()))
        else:
            physico_col = self._col("physico")
            toxico_col = self._col("toxico")
            micro_col = self._col("micro")
            subtotal_col = self._col("subtotal")
            quantity_widget = self.product_table.cellWidget(row, self._col("quantity"))
            quantity_value = self._parse_positive_int(quantity_widget.text() if quantity_widget else 1, default=1, minimum=1)
            analysis_duration_days = self._parse_positive_int(self.product_analysis_durations.get(pid, 0), default=0, minimum=0)
            if self.selected_products.get(pid, False):
                self.selected_quantities[pid] = quantity_value
            ref = 0
            if self._is_quantity_only_row_edit():
                return

        physico_widget = self.product_table.cellWidget(row, physico_col)
        toxico_widget = self.product_table.cellWidget(row, toxico_col)
        micro_widget = self.product_table.cellWidget(row, micro_col)

        physico = int(self.parse_number(physico_widget.text() if physico_widget else 0))
        toxico = int(self.parse_number(toxico_widget.text() if toxico_widget else 0))
        micro = int(self.parse_number(micro_widget.text() if micro_widget else 0))
        subtotal = physico + toxico + micro

        self.product_service.update_product(
            pid,
            ref,
            num_act if self.invoice_type == "standard" else None,
            physico,
            toxico,
            micro,
            subtotal,
            update_ref=False,
            analysis_duration_days=analysis_duration_days,
        )
        if analysis_duration_days is not None:
            self.product_analysis_durations[pid] = max(int(analysis_duration_days), 0)
        if self.invoice_type == "standard" and not self.selected_products.get(pid, False):
            num_act_widget = self.product_table.cellWidget(row, self._col("num_act"))
            if num_act_widget is not None:
                self._set_line_edit_text(num_act_widget, "")
        self.catalog_signature = self._safe_catalog_signature()

    def get_product_subtotal(self, product_id):
        row = self._find_row_for_product(product_id)
        if row < 0:
            return None

        subtotal_col = self._col("subtotal")
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

    def _compute_display_subtotal(self, unit_subtotal, quantity):
        qty = self._parse_positive_int(quantity, default=1, minimum=1)
        return self.parse_number(unit_subtotal) * qty

    def _current_row_quantity(self, row):
        quantity_widget = self.product_table.cellWidget(row, self._col("quantity"))
        return self._parse_positive_int(quantity_widget.text() if quantity_widget else 1, default=1, minimum=1)

    def _set_row_subtotal_display(self, row, unit_subtotal):
        subtotal_widget = self.product_table.cellWidget(row, self._col("subtotal"))
        if subtotal_widget is None:
            return
        display_subtotal = self._compute_display_subtotal(unit_subtotal, self._current_row_quantity(row))
        self._set_line_edit_text(subtotal_widget, self.format_number(display_subtotal))

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

    def _sync_visible_selected_num_acts(self):
        if self.invoice_type != "standard":
            return

        for row in range(self.product_table.rowCount()):
            item = self.product_table.item(row, 0)
            if not item:
                continue
            pid = item.data(Qt.UserRole)
            if pid is None or not self.selected_products.get(pid, False):
                continue
            num_act_widget = self.product_table.cellWidget(row, self._col("num_act"))
            if num_act_widget is None:
                continue
            self.selected_num_acts[pid] = str(num_act_widget.text()).strip()
            quantity_widget = self.product_table.cellWidget(row, self._col("quantity"))
            duration_widget = self.product_table.cellWidget(row, self._col("duration"))
            self.selected_quantities[pid] = self._parse_positive_int(quantity_widget.text() if quantity_widget else 1, default=1, minimum=1)
            self.selected_result_dates[pid] = self._compute_result_date_from_duration(
                self._parse_positive_int(duration_widget.text() if duration_widget else self.product_analysis_durations.get(pid, 0), default=0, minimum=0)
            )

    def validate_num_act_row(self, row):
        if self.invoice_type != "standard":
            return True
        num_act_widget = self.product_table.cellWidget(row, self._col("num_act"))
        if num_act_widget is None:
            return True

        current_item = self.product_table.item(row, 0)
        current_pid = current_item.data(Qt.UserRole) if current_item else None
        if current_pid is None or not self.selected_products.get(current_pid, False):
            return True

        quantity_widget = self.product_table.cellWidget(row, self._col("quantity"))
        quantity_value = self._parse_positive_int(quantity_widget.text() if quantity_widget else 1, default=1, minimum=1)
        series = self._normalize_num_act_series(num_act_widget.text(), quantity_value)
        self._set_line_edit_text(num_act_widget, self._format_num_act_series(series))

        self._sync_visible_selected_num_acts()
        self.selected_num_acts[current_pid] = self._format_num_act_series(series)

        seen_values = {}
        for pid in self.selection_order:
            if not self.selected_products.get(pid, False):
                continue
            designation_key = self._designation_key_for_pid(pid)
            pid_quantity = self.selected_quantities.get(pid, self.product_default_quantities.get(pid, 1))
            for item_num_act in self._normalize_num_act_series(self.selected_num_acts.get(pid), pid_quantity):
                if not item_num_act:
                    continue
                previous_entry = seen_values.get(item_num_act)
                if previous_entry and previous_entry["product_id"] != pid and previous_entry["designation_key"] != designation_key:
                    QMessageBox.warning(
                        self,
                        "N° Acte déjà utilisé",
                        f"Le N° Acte « {item_num_act} » est déjà utilisé par un autre produit dans cette facture.",
                    )
                    return False
                seen_values[item_num_act] = {
                    "product_id": pid,
                    "designation_key": designation_key,
                }

        return True

    def set_loaded_record_locked(self, locked):
        self.loaded_record_locked = bool(locked)
        self.add_product_btn.setEnabled(self._can_manage_product_catalog() and not self.loaded_record_locked)
        for row in range(self.product_table.rowCount()):
            self._update_row_action_state(row)

    def _update_row_action_state(self, row):
        btn_del_col = self._col("delete")
        btn_mod_col = self._col("edit")
        btn_sel_col = self._col("select")
        btn_del = self.product_table.cellWidget(row, btn_del_col)
        btn_mod = self.product_table.cellWidget(row, btn_mod_col)
        btn_sel = self.product_table.cellWidget(row, btn_sel_col)
        if btn_del:
            btn_del.setEnabled(self._can_manage_product_catalog() and not self.loaded_record_locked)
        if btn_mod:
            btn_mod.setEnabled(self._can_use_row_edit())
        if btn_sel:
            btn_sel.setEnabled(not self.loaded_record_locked)

    def delete_product_row(self, pid, row):
        if not self._can_manage_product_catalog():
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
            physico_col = self._col("physico")
            toxico_col = self._col("toxico")
            micro_col = self._col("micro")
            subtotal_col = self._col("subtotal")
        else:  # proforma
            physico_col = self._col("physico")
            toxico_col = self._col("toxico")
            micro_col = self._col("micro")
            subtotal_col = self._col("subtotal")

        physico_widget = self.product_table.cellWidget(row, physico_col)
        toxico_widget = self.product_table.cellWidget(row, toxico_col)
        micro_widget = self.product_table.cellWidget(row, micro_col)

        physico = self.parse_number(physico_widget.text())
        toxico = self.parse_number(toxico_widget.text())
        micro = self.parse_number(micro_widget.text())

        subtotal_value = physico + toxico + micro
        self._set_row_subtotal_display(row, subtotal_value)

        pid = item.data(Qt.UserRole)
        quantity_widget = self.product_table.cellWidget(row, self._col("quantity"))
        quantity_value = self._parse_positive_int(quantity_widget.text() if quantity_widget else 1, default=1, minimum=1)
        duration_value = self._parse_positive_int(self.product_analysis_durations.get(pid, 0), default=0, minimum=0)
        if self.invoice_type == "standard":
            duration_widget = self.product_table.cellWidget(row, self._col("duration"))
            duration_value = self._parse_positive_int(duration_widget.text() if duration_widget else self.product_analysis_durations.get(pid, 0), default=0, minimum=0)
            num_act = str(self.product_table.cellWidget(row, self._col("num_act")).text()).strip()
            if self.selected_products.get(pid, False):
                self.selected_num_acts[pid] = num_act
                self.selected_quantities[pid] = quantity_value
                self.selected_result_dates[pid] = self._compute_result_date_from_duration(duration_value)

        if self.selected_products.get(pid, False):
            self.selected_quantities[pid] = quantity_value

        if self.selected_products.get(pid, False):
            self.selection_changed.emit()

    def _select_row_for_invoice(self, pid, row):
        btn = self.product_table.cellWidget(row, self._col("select"))
        if btn:
            btn.setText("Annuler")
        self.selected_products[pid] = True
        if pid not in self.selection_order:
            self.selection_order.append(pid)
        quantity_widget = self.product_table.cellWidget(row, self._col("quantity"))
        self.selected_quantities[pid] = self._parse_positive_int(quantity_widget.text() if quantity_widget else 1, default=1, minimum=1)
        if self.invoice_type == "standard":
            duration_widget = self.product_table.cellWidget(row, self._col("duration"))
            num_act_widget = self.product_table.cellWidget(row, self._col("num_act"))
            current_num_act = str(num_act_widget.text() if num_act_widget else "").strip()
            self.selected_num_acts[pid] = current_num_act
            self.selected_result_dates[pid] = self._compute_result_date_from_duration(
                self._parse_positive_int(duration_widget.text() if duration_widget else self.product_analysis_durations.get(pid, 0), default=0, minimum=0)
            )
        self.apply_selection_style(row)

    def _should_auto_select_standard_row(self, row, pid):
        if self.invoice_type != "standard":
            return False
        if self.selected_products.get(pid, False):
            return False
        num_act_widget = self.product_table.cellWidget(row, self._col("num_act"))
        if num_act_widget is None:
            return False
        return bool(str(num_act_widget.text()).strip())

    def toggle_select(self, pid, row):
        if self.loaded_record_locked:
            return
        btn_col = self._col("select")
        btn = self.product_table.cellWidget(row, btn_col)
        currently_selected = bool(self.selected_products.get(pid, False))

        if not currently_selected:
            # Select: mark and append to order
            self._select_row_for_invoice(pid, row)
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
            if pid in self.selected_result_dates:
                del self.selected_result_dates[pid]
            if pid in self.selected_quantities:
                del self.selected_quantities[pid]
            self.clear_selection_style(row)
            if self.invoice_type == "standard":
                num_act_widget = self.product_table.cellWidget(row, self._col("num_act"))
                if num_act_widget is not None:
                    self._set_line_edit_text(num_act_widget, "")

        # Refresh displayed refs for standard rows according to selected_refs mapping
        self._refresh_preview_refs()
        self.selection_changed.emit()

    def _refresh_preview_refs(self):
        if self.invoice_type != "standard":
            return

        persisted_refs = {}
        for pid in self.selection_order:
            if pid in self.selected_products and self.selected_products[pid] and pid in self.selected_refs:
                persisted_refs[pid] = list(self.selected_refs[pid]) if isinstance(self.selected_refs[pid], list) else [self.selected_refs[pid]]

        preview_refs = {pid: list(values) for pid, values in persisted_refs.items()}
        try:
            next_ref = int(self.product_service.get_max_ref_b_analyse() or 0) + 1
        except Exception:
            next_ref = 1

        for pid in self.selection_order:
            if not self.selected_products.get(pid, False):
                continue
            quantity_value = self.selected_quantities.get(pid, 1)
            refs = list(preview_refs.get(pid, []))
            while len(refs) < quantity_value:
                refs.append(next_ref)
                next_ref += 1
            preview_refs[pid] = refs[:quantity_value]

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
                ref_widget = self.product_table.cellWidget(row, self._col("ref"))
                if ref_widget is None:
                    continue
                display_value = self._format_ref_preview(ref_mapping.get(pid)) if pid in ref_mapping else "0"
                ref_widget.setText(display_value)

    def apply_selection_style(self, row):
        for col in range(self.product_table.columnCount()):
            item = self.product_table.item(row, col)
            if item:
                item.setBackground(QColor("#2F5A8F"))
                item.setForeground(QColor("white"))
        if self.invoice_type == "standard":
            editable_cols = [self._col("quantity"), self._col("duration"), self._col("ref"), self._col("num_act"), self._col("physico"), self._col("toxico"), self._col("micro")]
        else:
            editable_cols = [self._col("quantity"), self._col("physico"), self._col("toxico"), self._col("micro")]
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
            editable_cols = [self._col("quantity"), self._col("duration"), self._col("ref"), self._col("num_act"), self._col("physico"), self._col("toxico"), self._col("micro")]
        else:
            editable_cols = [self._col("quantity"), self._col("physico"), self._col("toxico"), self._col("micro")]
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

    def select_products(self, product_ids, ref_mapping=None, num_act_mapping=None, result_date_mapping=None, line_items=None):
        ref_mapping = ref_mapping or {}
        num_act_mapping = num_act_mapping or {}
        result_date_mapping = result_date_mapping or {}
        aggregated_items = {}
        if line_items:
            for line in line_items:
                pid = line.get("product_id")
                if pid is None:
                    continue
                bucket = aggregated_items.setdefault(pid, {"count": 0, "refs": [], "num_acts": [], "result_date": None})
                bucket["count"] += self._parse_positive_int(line.get("quantity"), default=1, minimum=1)
                if line.get("ref_b_analyse") is not None:
                    bucket["refs"].append(int(line.get("ref_b_analyse")))
                if str(line.get("num_act") or "").strip():
                    bucket["num_acts"].append(str(line.get("num_act")).strip())
                if str(line.get("result_date") or "").strip() and not bucket["result_date"]:
                    bucket["result_date"] = str(line.get("result_date")).strip()
            product_ids = [line.get("product_id") for line in line_items if line.get("product_id") is not None]

        seen_pids = []
        for pid in product_ids:
            if pid in seen_pids:
                continue
            seen_pids.append(pid)
            already_selected = self.selected_products.get(pid, False)
            if not already_selected:
                self.selected_products[pid] = True
                if pid not in self.selection_order:
                    self.selection_order.append(pid)
            if self.invoice_type == "standard":
                if pid in aggregated_items:
                    if aggregated_items[pid]["refs"]:
                        self.selected_refs[pid] = list(aggregated_items[pid]["refs"])
                    self.selected_num_acts[pid] = self._format_num_act_series(aggregated_items[pid]["num_acts"])
                    self.selected_result_dates[pid] = str(aggregated_items[pid]["result_date"] or self._compute_result_date_from_duration(self.product_analysis_durations.get(pid, 0)) or "").strip()
                    self.selected_quantities[pid] = aggregated_items[pid]["count"]
                else:
                    existing_ref = ref_mapping.get(pid)
                    if existing_ref is not None:
                        self.selected_refs[pid] = list(existing_ref) if isinstance(existing_ref, list) else [int(existing_ref)]
                    self.selected_num_acts[pid] = self._format_num_act_series(num_act_mapping.get(pid))
                    self.selected_result_dates[pid] = str(result_date_mapping.get(pid) or self._compute_result_date_from_duration(self.product_analysis_durations.get(pid, 0)) or "").strip()
                    self.selected_quantities[pid] = 1
            else:
                self.selected_quantities[pid] = aggregated_items.get(pid, {}).get("count") or 1
            # Trouver la ligne et appliquer la sélection UI
            for row in range(self.product_table.rowCount()):
                row_item = self.product_table.item(row, 0)
                if not row_item:
                    continue
                item_pid = row_item.data(Qt.UserRole)
                if item_pid == pid:
                    quantity_widget = self.product_table.cellWidget(row, self._col("quantity"))
                    if quantity_widget is not None:
                        quantity_widget.setText(str(self.selected_quantities.get(pid, 1)))
                    product = self.product_service.get_product_by_id(pid)
                    if product:
                        self._set_row_subtotal_display(row, product.get("subtotal", 0))
                    if self.invoice_type == "standard":
                        num_act_widget = self.product_table.cellWidget(row, self._col("num_act"))
                        if num_act_widget is not None:
                            num_act_widget.setText(self._format_num_act_series(self.selected_num_acts.get(pid) or ""))
                    btn_col = self._col("select")
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
        self.product_default_quantities = {}
        self.product_analysis_durations = {}
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
                self.product_default_quantities[pid] = 1
                self.product_analysis_durations[pid] = int(product.get('analysis_duration_days') or 0)
                name = product['product_name']
                default_quantity = 1
                duration_days = product.get('analysis_duration_days') or 0
                ref = 0
                num_act = ""
                physico = product['physico']
                toxico = product['toxico']
                micro = product['micro']
                subtotal = product['subtotal']
                self.add_product_row(pid, name, default_quantity, duration_days, ref, num_act, physico, toxico, micro, subtotal)
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
        self._show_catalog_notification("Le catalogue a été mis à jour automatiquement.")

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
        self.catalog_notification.setStyleSheet(
            "background-color: #264b2f; color: white; border: 1px solid #4b8a58; border-radius: 4px; padding: 6px 10px;"
        )
        self.catalog_notice_timer.start(4000)

    def _clear_catalog_notification(self):
        self.catalog_notification.setText("")
        self.catalog_notification.setStyleSheet(
            "background: transparent; color: transparent; border: 1px solid transparent; padding: 6px 10px;"
        )

    def _cancel_edit_if_active(self, row):
        """If a row is in edit mode (widgets not-readonly), cancel it cleanly."""
        if self.invoice_type == "standard":
            widget_col, btn_mod_col = self._col("num_act"), self._col("edit")
        else:
            widget_col, btn_mod_col = self._col("quantity"), self._col("edit")
        editable_cols = self._editable_row_columns()
        amount_cols = [self._col("physico"), self._col("toxico"), self._col("micro")]
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
        elif not self._is_quantity_only_row_edit():
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
        self.selected_result_dates.clear()
        self.selected_quantities.clear()

        # Nettoyer l'UI des lignes visibles
        for row in range(self.product_table.rowCount()):
            btn_col = self._col("select")
            btn = self.product_table.cellWidget(row, btn_col)
            if btn:
                btn.setText("Choisir")
            self.clear_selection_style(row)
            if self.invoice_type == "standard":
                num_act_widget = self.product_table.cellWidget(row, self._col("num_act"))
                if num_act_widget:
                    num_act_widget.setText("")
            quantity_widget = self.product_table.cellWidget(row, self._col("quantity"))
            if quantity_widget:
                quantity_widget.setText("1")
            item = self.product_table.item(row, 0)
            if item:
                product = self.product_service.get_product_by_id(item.data(Qt.UserRole))
                if product:
                    self._set_row_subtotal_display(row, product.get("subtotal", 0))
        self.enable_form_fields()
        # Renumber UI refs to reflect cleared selections
        self._refresh_preview_refs()
        self.selection_changed.emit()

    def build_selected_line_items(self, allocate_missing_refs=False, start_ref=None, persist_allocations=False):
        self._sync_visible_selected_num_acts()
        next_ref = int(start_ref or 1)
        line_items = []
        for pid in self.selection_order:
            if not self.selected_products.get(pid, False):
                continue
            quantity = self.selected_quantities.get(pid, 1)
            if self.invoice_type != "standard":
                line_items.append(
                    {
                        "product_id": pid,
                        "quantity": quantity,
                    }
                )
                continue
            refs = self.selected_refs.get(pid)
            refs = list(refs) if isinstance(refs, list) else ([int(refs)] if refs is not None else [])
            if allocate_missing_refs:
                while len(refs) < quantity:
                    refs.append(next_ref)
                    next_ref += 1
                if persist_allocations:
                    self.selected_refs[pid] = list(refs)
            result_date = str(self.selected_result_dates.get(pid) or self._compute_result_date_from_duration(self.product_analysis_durations.get(pid, 0)) or "").strip()
            num_act_values = self._normalize_num_act_series(self.selected_num_acts.get(pid), quantity)
            for index in range(quantity):
                line_items.append(
                    {
                        "product_id": pid,
                        "occurrence_index": index + 1,
                        "ref_b_analyse": refs[index] if index < len(refs) else None,
                        "num_act": num_act_values[index] if index < len(num_act_values) else None,
                        "result_date": result_date or None,
                    }
                )
        return line_items

    def get_preview_line_items(self):
        start_ref = int(self.product_service.get_max_ref_b_analyse() or 0) + 1 if self.invoice_type == "standard" else 1
        return self.build_selected_line_items(
            allocate_missing_refs=self.invoice_type == "standard",
            start_ref=start_ref,
            persist_allocations=False,
        )

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

