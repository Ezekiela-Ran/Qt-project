"""
Popup de sélection des types de certificat (CC / CNC) par produit sélectionné.
Chaque produit est soit CC (Consommable) soit CNC (Non Consommable), pas les deux.
Des champs de saisie par produit permettent de renseigner les informations qui
apparaîtront dans le modèle de certificat imprimé.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QCheckBox, QWidget, QAbstractItemView, QLabel, QHeaderView,
    QMessageBox, QLineEdit, QDateEdit,
)
from PySide6.QtCore import Qt, QDate, QSignalBlocker, QTimer, Signal

from views.certificate.certificate_printer import CertificatePrinter
from utils.path_utils import resolve_resource_path

# ------------------------------------------------------------------
# Indices de colonnes
# ------------------------------------------------------------------
_COL_DESIGNATION    = 0
_COL_CC             = 1
_COL_CNC            = 2
_COL_QTE            = 3
_COL_QTE_ANALYSEE   = 4
_COL_NUM_LOT        = 5
_COL_NUM_ACTE       = 6
_COL_CLASSE         = 7
_COL_DATE_PROD      = 8
_COL_DATE_PEREMP    = 9
_COL_NUM_PRELEV     = 10
_COL_DATE_PV        = 11
_COL_DATE_CERT      = 12
_COL_ACTIONS        = 13
_COL_COUNT          = 14

CERTIFICATE_REFRESH_INTERVAL_MS = 5000

_HEADERS = [
    "Désignation",
    "CC",
    "CNC",
    "Quantité *",
    "Qté Analysée *",
    "N° Lot *",
    "N° Acte",
    "Classe *",
    "Date de production",
    "Date de péremption",
    "N° PRL",
    "Date commerce",
    "Date cert *",
    "Actions",
]


class OptionalDateEdit(QDateEdit):
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDateRange(QDate(1900, 1, 1), QDate(7999, 12, 31))
        self.setDisplayFormat("dd/MM/yyyy")
        self.setSpecialValueText("")
        self.setMinimumWidth(112)
        self.setProperty("user_modified", False)
        self.setProperty("loading_value", False)
        self._set_empty_state()

    def _set_empty_state(self):
        self.setDate(self.minimumDate())
        line_edit = self.lineEdit()
        if line_edit is not None:
            line_edit.clear()

    def clear_date(self):
        self.setProperty("loading_value", True)
        try:
            self._set_empty_state()
        finally:
            self.setProperty("loading_value", False)
        self.setProperty("user_modified", False)
        self.cleared.emit()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.clear_date()
            event.accept()
            return

        super().keyPressEvent(event)


class CertificateDialog(QDialog):
    """
    Dialogue de sélection CC / CNC avec champs de saisie par produit.

    Paramètres
    ----------
    parent           : widget parent (body_layout)
    form             : formulaire client actif
    selected_products: liste ordonnée de product_id sélectionnés
    db_manager       : DatabaseManager pour résoudre les noms de produits
    product_manager  : ProductManager (optionnel) pour pré-remplir N° Acte
    """

    def __init__(self, parent, form, selected_products, db_manager, invoice_id=None, invoice_type="standard", product_manager=None):
        super().__init__(parent)
        self.form = form
        self.selected_products = selected_products
        self.db_manager = db_manager
        self.invoice_id = invoice_id
        self.invoice_type = invoice_type or "standard"
        self.product_manager = product_manager
        self._rows: list[dict] = []
        self._printer = CertificatePrinter(self)
        self._refresh_pending = False
        self._is_refreshing = False
        self._last_entries_signature: tuple = ()

        self.setWindowTitle("Certificats — CC / CNC")
        self.setModal(True)

        self._build_ui()
        self._load_products()
        self._init_refresh_timer()
        self._apply_screen_geometry()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        title = QLabel(
            "Remplir les informations pour chaque produit, sélectionner CC ou CNC, enregistrer puis imprimer"
        )
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 13px; margin-bottom: 4px;")
        layout.addWidget(title)

        required_note = QLabel(
            "Les champs marqués * sont obligatoires. Le N° certificat est attribué automatiquement à l'enregistrement et ne peut plus être modifié ensuite."
        )
        required_note.setAlignment(Qt.AlignCenter)
        required_note.setStyleSheet("color: #2F5A8F; font-weight: bold; margin-bottom: 6px;")
        layout.addWidget(required_note)

        self._table = QTableWidget()
        self._table.setColumnCount(_COL_COUNT)
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(_COL_DESIGNATION, QHeaderView.Stretch)
        for col in (
            _COL_QTE,
            _COL_QTE_ANALYSEE,
            _COL_NUM_LOT,
            _COL_NUM_ACTE,
            _COL_CLASSE,
            _COL_DATE_PROD,
            _COL_DATE_PEREMP,
            _COL_NUM_PRELEV,
            _COL_DATE_PV,
            _COL_DATE_CERT,
        ):
            hdr.setSectionResizeMode(col, QHeaderView.Interactive)
            self._table.setColumnWidth(col, 104)
        self._table.setColumnWidth(_COL_QTE, 96)
        self._table.setColumnWidth(_COL_QTE_ANALYSEE, 96)
        self._table.setColumnWidth(_COL_NUM_LOT, 96)
        self._table.setColumnWidth(_COL_NUM_ACTE, 96)
        self._table.setColumnWidth(_COL_CLASSE, 92)
        self._table.setColumnWidth(_COL_DATE_PROD, 112)
        self._table.setColumnWidth(_COL_DATE_PEREMP, 112)
        self._table.setColumnWidth(_COL_NUM_PRELEV, 88)
        self._table.setColumnWidth(_COL_DATE_PV, 112)
        self._table.setColumnWidth(_COL_DATE_CERT, 112)
        hdr.setSectionResizeMode(_COL_CC, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(_COL_CNC, QHeaderView.ResizeToContents)

        hdr.setSectionResizeMode(_COL_ACTIONS, QHeaderView.ResizeToContents)

        layout.addWidget(self._table)

    def _apply_screen_geometry(self):
        parent_window = self.parentWidget().window() if self.parentWidget() else None
        screen = parent_window.screen() if parent_window else self.screen()
        if screen is None:
            self.resize(1600, 520)
            return

        available_geometry = screen.availableGeometry()
        target_height = min(max(520, self.sizeHint().height()), available_geometry.height())
        self.setGeometry(
            available_geometry.x(),
            available_geometry.y(),
            available_geometry.width(),
            target_height,
        )

    def _init_refresh_timer(self):
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(CERTIFICATE_REFRESH_INTERVAL_MS)
        self.refresh_timer.timeout.connect(self.refresh_certificate_entries_silently)
        self.refresh_timer.start()

    def _load_products(self):
        invoice_item_map, saved_entries = self._fetch_certificate_source_data()
        self._last_entries_signature = self._build_entries_signature(saved_entries)

        self._table.setRowCount(len(self.selected_products))
        for i, pid in enumerate(self.selected_products):
            product = self.db_manager.get_product_by_id(pid)
            name = product["product_name"] if product else f"Produit {pid}"
            item_info = invoice_item_map.get(pid, {})
            num_acte = (item_info.get("num_act") if item_info else "") or ""
            if self.product_manager:
                num_acte = self.product_manager.selected_num_acts.get(pid, "") or ""
            self._add_row(
                i,
                pid,
                name,
                {
                    "num_act": num_acte,
                    "ref_b_analyse": (item_info.get("ref_b_analyse") if item_info else None) or (product.get("ref_b_analyse") if product else None),
                },
                saved_entries.get(pid, {}),
            )

    def _fetch_certificate_source_data(self):
        invoice_item_map = {}
        saved_entries = {}
        if not self.invoice_id:
            return invoice_item_map, saved_entries

        for entry in self.db_manager.get_invoice_items_with_refs(self.invoice_id, self.invoice_type):
            invoice_item_map[entry["product_id"]] = entry

        for entry in self.db_manager.get_certificate_entries(self.invoice_id, self.invoice_type, self.selected_products):
            saved_entries.setdefault(entry["product_id"], {})[entry["certificate_type"]] = entry

        return invoice_item_map, saved_entries

    def _add_row(self, row_index: int, pid, name: str, base_defaults: dict | None = None, saved_entries: dict | None = None):
        """Ajoute une ligne avec champs de saisie et choix CC / CNC."""
        base_defaults = base_defaults or {}
        saved_entries = saved_entries or {}

        item = QTableWidgetItem(name)
        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._table.setItem(row_index, _COL_DESIGNATION, item)

        qty_edit          = self._make_line_edit("ex: 10 kg", 96)
        qty_analysee_edit = self._make_line_edit("ex: 10 kg", 96)
        num_lot_edit      = self._make_line_edit("N° Lot", 96)
        num_acte_edit     = self._make_line_edit("N° Acte", 96)
        num_acte_edit.setText(str(base_defaults.get("num_act") or ""))
        classe_edit       = self._make_line_edit("Classe", 92)
        date_prod_edit   = self._make_date_edit()
        date_peremp_edit = self._make_date_edit()
        num_prelev_edit  = self._make_line_edit("N° PRL", 88)
        date_pv_edit     = self._make_date_edit()
        date_cert_edit   = self._make_date_edit()

        self._table.setCellWidget(row_index, _COL_QTE,            qty_edit)
        self._table.setCellWidget(row_index, _COL_QTE_ANALYSEE,   qty_analysee_edit)
        self._table.setCellWidget(row_index, _COL_NUM_LOT,        num_lot_edit)
        self._table.setCellWidget(row_index, _COL_NUM_ACTE,       num_acte_edit)
        self._table.setCellWidget(row_index, _COL_CLASSE,         classe_edit)
        self._table.setCellWidget(row_index, _COL_DATE_PROD,      date_prod_edit)
        self._table.setCellWidget(row_index, _COL_DATE_PEREMP,    date_peremp_edit)
        self._table.setCellWidget(row_index, _COL_NUM_PRELEV,     num_prelev_edit)
        self._table.setCellWidget(row_index, _COL_DATE_PV,        date_pv_edit)
        self._table.setCellWidget(row_index, _COL_DATE_CERT,      date_cert_edit)

        cc_container  = self._make_centered_checkbox()
        cnc_container = self._make_centered_checkbox()
        actual_cc  = cc_container.findChild(QCheckBox)
        actual_cnc = cnc_container.findChild(QCheckBox)
        check_icon = resolve_resource_path("images/checkbox-check-white.svg").as_posix()
        checkbox_style = (
            "QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid white; background: transparent; }"
            f"QCheckBox::indicator:checked {{ image: url({check_icon}); border: 1px solid white; background: transparent; }}"
        )
        actual_cc.setStyleSheet(checkbox_style)
        actual_cnc.setStyleSheet(checkbox_style)
        _wire_exclusive(actual_cc, actual_cnc)
        actual_cc.toggled.connect(lambda checked, r=row_index: checked and self._on_certificate_type_selected(r, "CC"))
        actual_cnc.toggled.connect(lambda checked, r=row_index: checked and self._on_certificate_type_selected(r, "CNC"))
        self._table.setCellWidget(row_index, _COL_CC,  cc_container)
        self._table.setCellWidget(row_index, _COL_CNC, cnc_container)

        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)
        btn_save = QPushButton("Enregistrer")
        btn_save.setObjectName("certificateSaveButton")
        btn_print = QPushButton("Imprimer")
        btn_print.setObjectName("certificatePrintButton")
        btn_save.clicked.connect(lambda _, r=row_index: self._on_row_save_clicked(r))
        btn_print.clicked.connect(lambda _, r=row_index: self._on_row_print_clicked(r))
        action_layout.addWidget(btn_save)
        action_layout.addWidget(btn_print)
        self._table.setCellWidget(row_index, _COL_ACTIONS, action_container)

        row_data = {
            "pid":              pid,
            "name":             name,
            "cc_cb":            actual_cc,
            "cnc_cb":           actual_cnc,
            "qty_edit":         qty_edit,
            "qty_analysee_edit": qty_analysee_edit,
            "num_lot_edit":     num_lot_edit,
            "num_acte_edit":    num_acte_edit,
            "classe_edit":      classe_edit,
            "date_prod_edit":   date_prod_edit,
            "date_peremp_edit": date_peremp_edit,
            "num_prelev_edit":  num_prelev_edit,
            "date_pv_edit":     date_pv_edit,
            "date_cert_edit":   date_cert_edit,
            "btn_save":         btn_save,
            "btn_print":        btn_print,
            "ref_b_analyse":    base_defaults.get("ref_b_analyse"),
            "base_defaults":    dict(base_defaults),
            "cached_entries":   {
                "CC": self._entry_to_payload(saved_entries.get("CC"), base_defaults),
                "CNC": self._entry_to_payload(saved_entries.get("CNC"), base_defaults),
            },
            "active_cert_type": None,
            "loading":         False,
        }

        if not saved_entries.get("CC"):
            row_data["cached_entries"]["CC"] = self._default_entry_to_payload(base_defaults)
        if not saved_entries.get("CNC"):
            row_data["cached_entries"]["CNC"] = self._default_entry_to_payload(base_defaults)
        self._rows.append(row_data)

        for widget in (
            qty_edit,
            qty_analysee_edit,
            num_lot_edit,
            num_acte_edit,
            classe_edit,
            num_prelev_edit,
        ):
            widget.editingFinished.connect(lambda r=row_index: self._on_row_data_changed(r))
        date_prod_edit.dateChanged.connect(lambda _date, r=row_index, e=date_prod_edit: self._on_date_edit_changed(r, e))
        date_peremp_edit.dateChanged.connect(lambda _date, r=row_index, e=date_peremp_edit: self._on_date_edit_changed(r, e))
        date_pv_edit.dateChanged.connect(lambda _date, r=row_index, e=date_pv_edit: self._on_date_edit_changed(r, e))
        date_cert_edit.dateChanged.connect(lambda _date, r=row_index, e=date_cert_edit: self._on_date_edit_changed(r, e))
        date_prod_edit.cleared.connect(lambda r=row_index: self._on_row_data_changed(r))
        date_peremp_edit.cleared.connect(lambda r=row_index: self._on_row_data_changed(r))
        date_pv_edit.cleared.connect(lambda r=row_index: self._on_row_data_changed(r))
        date_cert_edit.cleared.connect(lambda r=row_index: self._on_row_data_changed(r))

        if saved_entries.get("CNC"):
            actual_cnc.setChecked(True)
        elif saved_entries.get("CC"):
            actual_cc.setChecked(True)
        else:
            self._set_row_action_state(row_data)

    @staticmethod
    def _make_centered_checkbox() -> QWidget:
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        lay.addWidget(QCheckBox())
        return container

    @staticmethod
    def _make_date_edit() -> OptionalDateEdit:
        edit = OptionalDateEdit()
        return edit

    @staticmethod
    def _date_edit_value(edit: QDateEdit) -> str:
        if not bool(edit.property("user_modified")):
            return ""
        if edit.date() == edit.minimumDate():
            return ""
        return edit.date().toString("dd/MM/yyyy")

    @staticmethod
    def _legacy_date_was_modified(value: str) -> bool:
        text = str(value or "").strip()
        if not text:
            return False
        return text != QDate.currentDate().toString("dd/MM/yyyy")

    @classmethod
    def _extract_date_payload(cls, entry: dict | None, value_key: str, modified_key: str) -> tuple[str, bool]:
        value = str((entry or {}).get(value_key) or "").strip()
        modified = (entry or {}).get(modified_key)
        if modified is None:
            legacy_modified = cls._legacy_date_was_modified(value)
            return (value if legacy_modified else "", legacy_modified)

        is_modified = bool(modified)
        return (value if is_modified else "", is_modified)

    @staticmethod
    def _make_line_edit(placeholder: str, width: int) -> QLineEdit:
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.setMaximumWidth(width)
        return edit

    @classmethod
    def _default_entry_to_payload(cls, base_defaults: dict | None = None) -> dict:
        payload = cls._entry_to_payload(None, base_defaults)
        payload["date_cert"] = QDate.currentDate().toString("dd/MM/yyyy")
        payload["date_cert_modified"] = True
        return payload

    @staticmethod
    def _entry_to_payload(entry: dict | None, base_defaults: dict | None = None) -> dict:
        base_defaults = base_defaults or {}
        date_production, date_production_modified = CertificateDialog._extract_date_payload(
            entry,
            "date_production",
            "date_production_modified",
        )
        date_peremption, date_peremption_modified = CertificateDialog._extract_date_payload(
            entry,
            "date_peremption",
            "date_peremption_modified",
        )
        date_commerce, date_commerce_modified = CertificateDialog._extract_date_payload(
            entry,
            "date_commerce",
            "date_commerce_modified",
        )
        date_cert, date_cert_modified = CertificateDialog._extract_date_payload(
            entry,
            "date_cert",
            "date_cert_modified",
        )
        return {
            "quantity": str((entry or {}).get("quantity") or "").strip(),
            "quantity_analysee": str((entry or {}).get("quantity_analysee") or "").strip(),
            "num_lot": str((entry or {}).get("num_lot") or "").strip(),
            "num_act": str((entry or {}).get("num_act") or base_defaults.get("num_act") or "").strip(),
            "num_cert": str((entry or {}).get("num_cert") or "").strip(),
            "classe": str((entry or {}).get("classe") or "").strip(),
            "date_production": date_production,
            "date_production_modified": date_production_modified,
            "date_peremption": date_peremption,
            "date_peremption_modified": date_peremption_modified,
            "num_prl": str((entry or {}).get("num_prl") or "").strip(),
            "date_commerce": date_commerce,
            "date_commerce_modified": date_commerce_modified,
            "date_cert": date_cert,
            "date_cert_modified": date_cert_modified,
        }

    @staticmethod
    def _payload_signature(payload: dict | None) -> tuple:
        payload = payload or {}
        return tuple(sorted(payload.items()))

    @classmethod
    def _build_entries_signature(cls, saved_entries: dict) -> tuple:
        signature = []
        for pid in sorted(saved_entries):
            entries = saved_entries[pid]
            for cert_type in sorted(entries):
                signature.append(
                    (
                        pid,
                        cert_type,
                        cls._payload_signature(cls._entry_to_payload(entries.get(cert_type))),
                    )
                )
        return tuple(signature)

    @staticmethod
    def _parse_date_value(value: str) -> QDate:
        parsed = QDate.fromString(str(value or "").strip(), "dd/MM/yyyy")
        return parsed if parsed.isValid() else QDate.currentDate()

    @staticmethod
    def _set_date_edit_state(edit: QDateEdit, value: str, user_modified: bool = False):
        text = str(value or "").strip()
        edit.setProperty("loading_value", True)
        try:
            if text and user_modified:
                edit.setDate(CertificateDialog._parse_date_value(text))
                edit.setProperty("user_modified", True)
            else:
                if isinstance(edit, OptionalDateEdit):
                    edit._set_empty_state()
                else:
                    edit.setDate(edit.minimumDate())
                edit.setProperty("user_modified", False)
        finally:
            edit.setProperty("loading_value", False)

    def _on_date_edit_changed(self, row_index: int, edit: QDateEdit):
        if bool(edit.property("loading_value")):
            return
        edit.setProperty("user_modified", True)
        self._on_row_data_changed(row_index)

    def _load_row_values(self, row: dict, payload: dict):
        row["loading"] = True
        try:
            row["qty_edit"].setText(payload.get("quantity", ""))
            row["qty_analysee_edit"].setText(payload.get("quantity_analysee", ""))
            row["num_lot_edit"].setText(payload.get("num_lot", ""))
            row["num_acte_edit"].setText(payload.get("num_act", ""))
            row["classe_edit"].setText(payload.get("classe", ""))
            self._set_date_edit_state(
                row["date_prod_edit"],
                payload.get("date_production", ""),
                payload.get("date_production_modified", False),
            )
            self._set_date_edit_state(
                row["date_peremp_edit"],
                payload.get("date_peremption", ""),
                payload.get("date_peremption_modified", False),
            )
            row["num_prelev_edit"].setText(payload.get("num_prl", ""))
            self._set_date_edit_state(
                row["date_pv_edit"],
                payload.get("date_commerce", ""),
                payload.get("date_commerce_modified", False),
            )
            self._set_date_edit_state(
                row["date_cert_edit"],
                payload.get("date_cert", ""),
                payload.get("date_cert_modified", False),
            )
        finally:
            row["loading"] = False

    def _row_has_focus(self, row: dict) -> bool:
        widgets = (
            row["qty_edit"],
            row["qty_analysee_edit"],
            row["num_lot_edit"],
            row["num_acte_edit"],
            row["classe_edit"],
            row["date_prod_edit"],
            row["date_peremp_edit"],
            row["num_prelev_edit"],
            row["date_pv_edit"],
            row["date_cert_edit"],
            row["cc_cb"],
            row["cnc_cb"],
        )
        return any(widget.hasFocus() for widget in widgets)

    def _row_is_being_edited(self, row: dict) -> bool:
        return bool(row.get("loading")) or self._row_has_focus(row)

    def _apply_remote_entry_to_row(self, row: dict, cert_type: str, payload: dict):
        row["cached_entries"][cert_type] = payload
        if row.get("active_cert_type") != cert_type:
            return
        self._load_row_values(row, payload)
        self._set_row_action_state(row)

    def _apply_remote_checkbox_state(self, row: dict, saved_entry_by_type: dict):
        target_type = None
        if saved_entry_by_type.get("CNC"):
            target_type = "CNC"
        elif saved_entry_by_type.get("CC"):
            target_type = "CC"

        if target_type == row.get("active_cert_type"):
            return

        blockers = [QSignalBlocker(row["cc_cb"]), QSignalBlocker(row["cnc_cb"])]
        try:
            row["cc_cb"].setChecked(target_type == "CC")
            row["cnc_cb"].setChecked(target_type == "CNC")
        finally:
            del blockers

        row["active_cert_type"] = target_type
        if target_type is not None:
            self._load_row_values(row, row["cached_entries"].get(target_type) or self._default_entry_to_payload(row.get("base_defaults")))
        self._set_row_action_state(row)

    def _refresh_row_from_remote(self, row: dict, saved_entry_by_type: dict):
        for cert_type in ("CC", "CNC"):
            remote_entry = saved_entry_by_type.get(cert_type)
            if remote_entry:
                payload = self._entry_to_payload(remote_entry, row.get("base_defaults"))
            elif row.get("active_cert_type") == cert_type:
                payload = self._default_entry_to_payload(row.get("base_defaults"))
            else:
                payload = self._default_entry_to_payload(row.get("base_defaults"))
            self._apply_remote_entry_to_row(row, cert_type, payload)
        self._apply_remote_checkbox_state(row, saved_entry_by_type)

    def refresh_certificate_entries_silently(self):
        if not self.invoice_id or not self.isVisible() or self._is_refreshing:
            return

        try:
            _invoice_item_map, saved_entries = self._fetch_certificate_source_data()
        except Exception:
            return

        latest_signature = self._build_entries_signature(saved_entries)
        if latest_signature == self._last_entries_signature:
            return

        if any(self._row_is_being_edited(row) for row in self._rows):
            self._refresh_pending = True
            return

        self._is_refreshing = True
        try:
            for row in self._rows:
                self._refresh_row_from_remote(row, saved_entries.get(row["pid"], {}))
            self._last_entries_signature = latest_signature
            self._refresh_pending = False
        finally:
            self._is_refreshing = False

    def _snapshot_row_values(self, row: dict, cert_type: str | None = None) -> dict:
        current_type = cert_type or row.get("active_cert_type")
        current_payload = row["cached_entries"].get(current_type, {}) if current_type else {}
        return {
            "quantity": row["qty_edit"].text().strip(),
            "quantity_analysee": row["qty_analysee_edit"].text().strip(),
            "num_lot": row["num_lot_edit"].text().strip(),
            "num_act": row["num_acte_edit"].text().strip(),
            "num_cert": str(current_payload.get("num_cert") or "").strip(),
            "classe": row["classe_edit"].text().strip(),
            "date_production": self._date_edit_value(row["date_prod_edit"]),
            "date_production_modified": bool(row["date_prod_edit"].property("user_modified")),
            "date_peremption": self._date_edit_value(row["date_peremp_edit"]),
            "date_peremption_modified": bool(row["date_peremp_edit"].property("user_modified")),
            "num_prl": row["num_prelev_edit"].text().strip(),
            "date_commerce": self._date_edit_value(row["date_pv_edit"]),
            "date_commerce_modified": bool(row["date_pv_edit"].property("user_modified")),
            "date_cert": self._date_edit_value(row["date_cert_edit"]),
            "date_cert_modified": bool(row["date_cert_edit"].property("user_modified")),
        }

    def _persist_row_state(self, row: dict, cert_type: str | None = None):
        if not self.invoice_id:
            return

        current_type = cert_type or row.get("active_cert_type")
        if not current_type:
            return

        payload = row["cached_entries"].get(current_type) or self._snapshot_row_values(row)
        self.db_manager.save_certificate_entry(
            self.invoice_id,
            self.invoice_type,
            row["pid"],
            current_type,
            payload,
        )
        self.db_manager.replace_certificate_entry_type(
            self.invoice_id,
            self.invoice_type,
            row["pid"],
            current_type,
        )
        self._last_entries_signature = ()

    def _reset_certificate_cache(self, row: dict, cert_type: str):
        row["cached_entries"][cert_type] = self._default_entry_to_payload(row.get("base_defaults"))

    def _restore_certificate_type_selection(self, row: dict, cert_type: str, payload: dict):
        blockers = [QSignalBlocker(row["cc_cb"]), QSignalBlocker(row["cnc_cb"])]
        try:
            row["cc_cb"].setChecked(cert_type == "CC")
            row["cnc_cb"].setChecked(cert_type == "CNC")
        finally:
            del blockers

        row["active_cert_type"] = cert_type
        row["cached_entries"][cert_type] = payload
        self._load_row_values(row, payload)
        self._set_row_action_state(row)

    def _switch_numbered_certificate_type(self, row: dict, source_type: str, target_type: str) -> bool:
        source_payload = self._snapshot_row_values(row, source_type)
        row["cached_entries"][source_type] = source_payload
        try:
            migrated_payload = self.db_manager.switch_certificate_entry_type(
                self.invoice_id,
                self.invoice_type,
                row["pid"],
                source_type,
                target_type,
                source_payload,
            )
        except Exception as exc:
            self._restore_certificate_type_selection(row, source_type, source_payload)
            QMessageBox.critical(
                self,
                "Changement de type impossible",
                f"Le certificat « {row['name']} » n'a pas pu être basculé de {source_type} vers {target_type}.\n\n{exc}",
            )
            return False

        self._reset_certificate_cache(row, source_type)
        row["active_cert_type"] = target_type
        row["cached_entries"][target_type] = migrated_payload
        self._load_row_values(row, migrated_payload)
        self._last_entries_signature = ()
        self._set_row_action_state(row)
        if self._refresh_pending:
            self.refresh_certificate_entries_silently()
        return True

    def _on_certificate_type_selected(self, row_index: int, cert_type: str):
        row = self._rows[row_index]
        previous_type = row.get("active_cert_type")
        if previous_type and previous_type != cert_type:
            previous_payload = self._snapshot_row_values(row, previous_type)
            if str(previous_payload.get("num_cert") or "").strip():
                self._switch_numbered_certificate_type(row, previous_type, cert_type)
                return
            self._reset_certificate_cache(row, previous_type)

        row["active_cert_type"] = cert_type
        payload = row["cached_entries"].get(cert_type) or self._default_entry_to_payload({"num_act": row["num_acte_edit"].text().strip()})
        self._load_row_values(row, payload)
        row["cached_entries"][cert_type] = self._snapshot_row_values(row, cert_type)
        self._persist_row_state(row, cert_type)
        self._set_row_action_state(row)

    def _on_row_data_changed(self, row_index: int):
        row = self._rows[row_index]
        if row.get("loading"):
            return

        cert_type = row.get("active_cert_type")
        if not cert_type:
            return

        row["cached_entries"][cert_type] = self._snapshot_row_values(row, cert_type)
        self._persist_row_state(row, cert_type)
        self._set_row_action_state(row)
        if self._refresh_pending:
            self.refresh_certificate_entries_silently()

    def _set_row_action_state(self, row: dict):
        cert_type = row.get("active_cert_type")
        has_number = bool(cert_type and str((row["cached_entries"].get(cert_type) or {}).get("num_cert") or "").strip())
        row["btn_save"].setEnabled(cert_type is not None)
        row["btn_print"].setEnabled(has_number)

        if cert_type is None:
            row["btn_save"].setToolTip("Sélectionnez CC ou CNC avant d'enregistrer.")
            row["btn_print"].setToolTip("Enregistrez d'abord un certificat pour pouvoir imprimer.")
            return

        if has_number:
            num_cert = str((row["cached_entries"].get(cert_type) or {}).get("num_cert") or "").strip()
            row["btn_save"].setToolTip(f"N° certificat attribué : {num_cert}")
            row["btn_print"].setToolTip(f"Imprimer le certificat {cert_type} n° {num_cert}.")
            return

        row["btn_save"].setToolTip("Enregistrer pour attribuer automatiquement le N° certificat.")
        row["btn_print"].setToolTip("Enregistrez d'abord le certificat pour attribuer son numéro.")

    def _confirm_certificate_number_lock(self, row: dict, cert_type: str) -> bool:
        reply = QMessageBox.question(
            self,
            "Enregistrer le certificat",
            (
                f"Voulez-vous vraiment enregistrer le certificat {cert_type} pour « {row['name']} » ?\n\n"
                "Le N° certificat sera attribué automatiquement. Si vous changez plus tard entre CC et CNC, "
                "la numérotation sera réajustée automatiquement pour garder une suite cohérente."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _save_row_certificate(self, row_index: int, require_confirmation: bool = True, show_success: bool = True) -> bool:
        row = self._rows[row_index]
        cert_type = self._selected_certificate_type(row)
        if cert_type is None:
            QMessageBox.warning(
                self,
                "Type manquant",
                f"Veuillez sélectionner CC ou CNC pour « {row['name']} ».",
            )
            return False

        if not self._validate_required_fields(row_index):
            return False

        payload = self._snapshot_row_values(row, cert_type)
        is_first_allocation = not payload.get("num_cert")
        if is_first_allocation:
            if require_confirmation and not self._confirm_certificate_number_lock(row, cert_type):
                return False
            payload["num_cert"] = str(self.db_manager.allocate_next_cert_number(cert_type))

        row["cached_entries"][cert_type] = payload
        self._persist_row_state(row, cert_type)
        self._set_row_action_state(row)

        if show_success:
            QMessageBox.information(
                self,
                "Certificat enregistré",
                f"Le certificat {cert_type} de « {row['name']} » a été enregistré avec le N° {payload['num_cert']}.",
            )
        return True

    def _on_row_save_clicked(self, row_index: int):
        self._save_row_certificate(row_index, require_confirmation=True, show_success=True)

    # ------------------------------------------------------------------
    # Logique d'impression
    # ------------------------------------------------------------------

    def _row_extras(self, row_index: int) -> dict:
        r = self._rows[row_index]
        payload = self._snapshot_row_values(r)
        return {
            "quantite":          payload["quantity"],
            "quantite_analysee": payload["quantity_analysee"],
            "num_lot":           payload["num_lot"],
            "num_acte":          payload["num_act"],
            "num_cert":          payload["num_cert"],
            "classe":            payload["classe"],
            "date_production":   payload["date_production"],
            "date_peremption":   payload["date_peremption"],
            "num_prl":           payload["num_prl"],
            "date_commerce":     payload["date_commerce"],
            "date_cert":         payload["date_cert"],
            "ref_b_analyse":     r.get("ref_b_analyse") or "",
            "invoice_number":    self.invoice_id or "",
            "analyse":           self._build_analyse_text(r["pid"]),
        }

    def _validate_required_fields(self, row_index: int) -> bool:
        r = self._rows[row_index]
        required_fields = [
            ("Quantité", r["qty_edit"].text().strip(), r["qty_edit"]),
            ("Qté Analysée", r["qty_analysee_edit"].text().strip(), r["qty_analysee_edit"]),
            ("N° Lot", r["num_lot_edit"].text().strip(), r["num_lot_edit"]),
            ("Classe", r["classe_edit"].text().strip(), r["classe_edit"]),
            ("Date cert", self._date_edit_value(r["date_cert_edit"]), r["date_cert_edit"]),
        ]

        for label, value, widget in required_fields:
            if value:
                continue
            QMessageBox.warning(
                self,
                "Champ obligatoire",
                f"Le champ « {label} » est obligatoire pour « {r['name']} ».",
            )
            widget.setFocus()
            return False

        return True

    def _build_analyse_text(self, pid) -> str:
        """Construit la ligne Analyse selon les composantes non nulles (> 0 Ar)."""
        physico, micro, toxico = self._get_product_components(pid)

        analyses = []
        if physico > 0:
            analyses.append("Physico-chimique")
        if micro > 0:
            analyses.append("Microbiologique")
        if toxico > 0:
            analyses.append("Toxicologique")

        return ", ".join(analyses)

    @staticmethod
    def _to_float(value) -> float:
        text = str(value or "").replace(" ", "").replace("Ar", "").strip()
        try:
            return float(text) if text else 0.0
        except (TypeError, ValueError):
            return 0.0

    def _get_product_components(self, pid):
        """Lit physico/micro/toxico depuis la table visible, sinon fallback base."""
        if self.product_manager and hasattr(self.product_manager, "product_table"):
            table = self.product_manager.product_table
            for row in range(table.rowCount()):
                item = table.item(row, 0)
                if not item or item.data(Qt.UserRole) != pid:
                    continue

                if getattr(self.product_manager, "invoice_type", "standard") == "proforma":
                    physico_col, toxico_col, micro_col = 1, 2, 3
                else:
                    physico_col, toxico_col, micro_col = 3, 4, 5

                physico_w = table.cellWidget(row, physico_col)
                toxico_w = table.cellWidget(row, toxico_col)
                micro_w = table.cellWidget(row, micro_col)

                physico = self._to_float(physico_w.text() if physico_w else 0)
                micro = self._to_float(micro_w.text() if micro_w else 0)
                toxico = self._to_float(toxico_w.text() if toxico_w else 0)
                return physico, micro, toxico

        product = self.db_manager.get_product_by_id(pid) or {}
        return (
            self._to_float(product.get("physico", 0)),
            self._to_float(product.get("micro", 0)),
            self._to_float(product.get("toxico", 0)),
        )

    def _selected_certificate_type(self, row: dict) -> str | None:
        if row["cc_cb"].isChecked():
            return "CC"
        if row["cnc_cb"].isChecked():
            return "CNC"
        return None

    def _on_row_print_clicked(self, row_index: int):
        row = self._rows[row_index]
        cert_type = self._selected_certificate_type(row)
        if cert_type is None:
            QMessageBox.warning(
                self,
                "Type manquant",
                f"Veuillez sélectionner CC ou CNC pour « {row['name']} ».",
            )
            return

        payload = row["cached_entries"].get(cert_type) or {}
        if not str(payload.get("num_cert") or "").strip():
            QMessageBox.warning(
                self,
                "Certificat non enregistré",
                f"Veuillez d'abord enregistrer le certificat {cert_type} pour « {row['name']} » afin d'attribuer le N° certificat.",
            )
            return

        if not self._save_row_certificate(row_index, require_confirmation=False, show_success=False):
            return

        self._printer.print_certificates(
            self.form,
            [(row["pid"], row["name"], cert_type, self._row_extras(row_index))],
        )

    def closeEvent(self, event):
        if hasattr(self, "refresh_timer"):
            self.refresh_timer.stop()
        super().closeEvent(event)


# ------------------------------------------------------------------
# Utilitaires
# ------------------------------------------------------------------

def _wire_exclusive(cb_a: QCheckBox, cb_b: QCheckBox):
    """Rend cb_a et cb_b mutuellement exclusifs."""
    def on_a(checked, _b=cb_b):
        if checked:
            _b.blockSignals(True); _b.setChecked(False); _b.blockSignals(False)
    def on_b(checked, _a=cb_a):
        if checked:
            _a.blockSignals(True); _a.setChecked(False); _a.blockSignals(False)
    cb_a.toggled.connect(on_a)
    cb_b.toggled.connect(on_b)
