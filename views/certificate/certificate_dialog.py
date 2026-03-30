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
from PySide6.QtCore import Qt, QDate

from views.certificate.certificate_printer import CertificatePrinter
from utils.path_utils import resolve_resource_path

# ------------------------------------------------------------------
# Indices de colonnes
# ------------------------------------------------------------------
_COL_DESIGNATION    = 0
_COL_QTE            = 1
_COL_QTE_ANALYSEE   = 2
_COL_NUM_LOT        = 3
_COL_NUM_ACTE       = 4
_COL_NUM_CERT       = 5
_COL_CLASSE         = 6
_COL_DATE_PROD      = 7
_COL_DATE_PEREMP    = 8
_COL_NUM_PRELEV     = 9
_COL_DATE_PV        = 10
_COL_CC             = 11
_COL_CNC            = 12
_COL_IMPRIMER       = 13
_COL_COUNT          = 14

_HEADERS = [
    "Désignation",
    "Quantité *",
    "Qté Analysée *",
    "N° Lot *",
    "N° Acte",
    "N° Cert *",
    "Classe *",
    "Date de production",
    "Date de péremption",
    "N° PRL",
    "Date commerce",
    "CC",
    "CNC",
    "Imprimer",
]


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

        self.setWindowTitle("Certificats — CC / CNC")
        self.setModal(True)

        self._build_ui()
        self._load_products()
        self._apply_screen_geometry()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        title = QLabel(
            "Remplir les informations pour chaque produit, sélectionner CC ou CNC, puis imprimer"
        )
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 13px; margin-bottom: 4px;")
        layout.addWidget(title)

        required_note = QLabel(
            "Les champs marqués * sont obligatoires. N° Acte, Date de production, Date de péremption, N° PRL et Date commerce sont optionnels."
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
            _COL_NUM_CERT,
            _COL_CLASSE,
            _COL_DATE_PROD,
            _COL_DATE_PEREMP,
            _COL_NUM_PRELEV,
            _COL_DATE_PV,
        ):
            hdr.setSectionResizeMode(col, QHeaderView.Interactive)
            self._table.setColumnWidth(col, 104)
        self._table.setColumnWidth(_COL_QTE, 96)
        self._table.setColumnWidth(_COL_QTE_ANALYSEE, 96)
        self._table.setColumnWidth(_COL_NUM_LOT, 96)
        self._table.setColumnWidth(_COL_NUM_ACTE, 96)
        self._table.setColumnWidth(_COL_NUM_CERT, 96)
        self._table.setColumnWidth(_COL_CLASSE, 92)
        self._table.setColumnWidth(_COL_DATE_PROD, 112)
        self._table.setColumnWidth(_COL_DATE_PEREMP, 112)
        self._table.setColumnWidth(_COL_NUM_PRELEV, 88)
        self._table.setColumnWidth(_COL_DATE_PV, 112)
        hdr.setSectionResizeMode(_COL_CC, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(_COL_CNC, QHeaderView.ResizeToContents)

        hdr.setSectionResizeMode(_COL_IMPRIMER, QHeaderView.ResizeToContents)

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

    def _load_products(self):
        invoice_item_map = {}
        if self.invoice_id:
            for entry in self.db_manager.get_invoice_items_with_refs(self.invoice_id, self.invoice_type):
                invoice_item_map[entry["product_id"]] = entry

        saved_entries = {}
        if self.invoice_id:
            for entry in self.db_manager.get_certificate_entries(self.invoice_id, self.invoice_type, self.selected_products):
                saved_entries.setdefault(entry["product_id"], {})[entry["certificate_type"]] = entry

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
        num_cert_edit     = self._make_line_edit("N° Cert", 96)
        classe_edit       = self._make_line_edit("Classe", 92)
        date_prod_edit   = self._make_date_edit()
        date_peremp_edit = self._make_date_edit()
        num_prelev_edit  = self._make_line_edit("N° PRL", 88)
        date_pv_edit     = self._make_date_edit()

        self._table.setCellWidget(row_index, _COL_QTE,            qty_edit)
        self._table.setCellWidget(row_index, _COL_QTE_ANALYSEE,   qty_analysee_edit)
        self._table.setCellWidget(row_index, _COL_NUM_LOT,        num_lot_edit)
        self._table.setCellWidget(row_index, _COL_NUM_ACTE,       num_acte_edit)
        self._table.setCellWidget(row_index, _COL_NUM_CERT,       num_cert_edit)
        self._table.setCellWidget(row_index, _COL_CLASSE,         classe_edit)
        self._table.setCellWidget(row_index, _COL_DATE_PROD,      date_prod_edit)
        self._table.setCellWidget(row_index, _COL_DATE_PEREMP,    date_peremp_edit)
        self._table.setCellWidget(row_index, _COL_NUM_PRELEV,     num_prelev_edit)
        self._table.setCellWidget(row_index, _COL_DATE_PV,        date_pv_edit)

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

        btn_print = QPushButton("Imprimer")
        btn_print.setObjectName("certificatePrintButton")
        btn_print.clicked.connect(lambda _, r=row_index: self._on_row_print_clicked(r))
        self._table.setCellWidget(row_index, _COL_IMPRIMER, btn_print)

        row_data = {
            "pid":              pid,
            "name":             name,
            "cc_cb":            actual_cc,
            "cnc_cb":           actual_cnc,
            "qty_edit":         qty_edit,
            "qty_analysee_edit": qty_analysee_edit,
            "num_lot_edit":     num_lot_edit,
            "num_acte_edit":    num_acte_edit,
            "num_cert_edit":    num_cert_edit,
            "classe_edit":      classe_edit,
            "date_prod_edit":   date_prod_edit,
            "date_peremp_edit": date_peremp_edit,
            "num_prelev_edit":  num_prelev_edit,
            "date_pv_edit":     date_pv_edit,
            "btn_print":        btn_print,
            "ref_b_analyse":    base_defaults.get("ref_b_analyse"),
            "cached_entries":   {
                "CC": self._entry_to_payload(saved_entries.get("CC"), base_defaults),
                "CNC": self._entry_to_payload(saved_entries.get("CNC"), base_defaults),
            },
            "active_cert_type": None,
            "loading":         False,
        }
        self._rows.append(row_data)

        for widget in (
            qty_edit,
            qty_analysee_edit,
            num_lot_edit,
            num_acte_edit,
            num_cert_edit,
            classe_edit,
            num_prelev_edit,
        ):
            widget.editingFinished.connect(lambda r=row_index: self._on_row_data_changed(r))
        date_prod_edit.dateChanged.connect(lambda _date, r=row_index, e=date_prod_edit: self._on_date_edit_changed(r, e))
        date_peremp_edit.dateChanged.connect(lambda _date, r=row_index, e=date_peremp_edit: self._on_date_edit_changed(r, e))
        date_pv_edit.dateChanged.connect(lambda _date, r=row_index, e=date_pv_edit: self._on_date_edit_changed(r, e))

        if saved_entries.get("CC"):
            actual_cc.setChecked(True)
        elif saved_entries.get("CNC"):
            actual_cnc.setChecked(True)

    @staticmethod
    def _make_centered_checkbox() -> QWidget:
        container = QWidget()
        lay = QHBoxLayout(container)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignCenter)
        lay.addWidget(QCheckBox())
        return container

    @staticmethod
    def _make_date_edit() -> QDateEdit:
        edit = QDateEdit()
        edit.setCalendarPopup(True)
        edit.setDateRange(QDate(1900, 1, 1), QDate(7999, 12, 31))
        edit.setDisplayFormat("dd/MM/yyyy")
        edit.setDate(QDate.currentDate())
        edit.setMinimumWidth(112)
        edit.setProperty("user_modified", False)
        edit.setProperty("loading_value", False)
        return edit

    @staticmethod
    def _date_edit_value(edit: QDateEdit) -> str:
        return edit.date().toString("dd/MM/yyyy") if bool(edit.property("user_modified")) else ""

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
        }

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
                edit.setDate(QDate.currentDate())
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
            row["num_cert_edit"].setText(payload.get("num_cert", ""))
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
        finally:
            row["loading"] = False

    def _snapshot_row_values(self, row: dict) -> dict:
        return {
            "quantity": row["qty_edit"].text().strip(),
            "quantity_analysee": row["qty_analysee_edit"].text().strip(),
            "num_lot": row["num_lot_edit"].text().strip(),
            "num_act": row["num_acte_edit"].text().strip(),
            "num_cert": row["num_cert_edit"].text().strip(),
            "classe": row["classe_edit"].text().strip(),
            "date_production": self._date_edit_value(row["date_prod_edit"]),
            "date_production_modified": bool(row["date_prod_edit"].property("user_modified")),
            "date_peremption": self._date_edit_value(row["date_peremp_edit"]),
            "date_peremption_modified": bool(row["date_peremp_edit"].property("user_modified")),
            "num_prl": row["num_prelev_edit"].text().strip(),
            "date_commerce": self._date_edit_value(row["date_pv_edit"]),
            "date_commerce_modified": bool(row["date_pv_edit"].property("user_modified")),
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

    def _on_certificate_type_selected(self, row_index: int, cert_type: str):
        row = self._rows[row_index]
        previous_type = row.get("active_cert_type")
        if previous_type and previous_type != cert_type:
            row["cached_entries"][previous_type] = self._snapshot_row_values(row)
            self._persist_row_state(row, previous_type)

        row["active_cert_type"] = cert_type
        payload = row["cached_entries"].get(cert_type) or self._entry_to_payload(None, {"num_act": row["num_acte_edit"].text().strip()})
        self._load_row_values(row, payload)
        row["cached_entries"][cert_type] = self._snapshot_row_values(row)
        self._persist_row_state(row, cert_type)

    def _on_row_data_changed(self, row_index: int):
        row = self._rows[row_index]
        if row.get("loading"):
            return

        cert_type = row.get("active_cert_type")
        if not cert_type:
            return

        row["cached_entries"][cert_type] = self._snapshot_row_values(row)
        self._persist_row_state(row, cert_type)

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
            ("N° Cert", r["num_cert_edit"].text().strip(), r["num_cert_edit"]),
            ("Classe", r["classe_edit"].text().strip(), r["classe_edit"]),
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

        if not self._validate_required_fields(row_index):
            return

        row["cached_entries"][cert_type] = self._snapshot_row_values(row)
        self._persist_row_state(row, cert_type)

        self._printer.print_certificates(
            self.form,
            [(row["pid"], row["name"], cert_type, self._row_extras(row_index))],
        )


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
