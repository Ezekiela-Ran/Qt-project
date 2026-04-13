from datetime import datetime

from PySide6.QtCore import Qt, QDate, QSignalBlocker, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QDateEdit,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from utils.path_utils import resolve_resource_path
from models.database_manager import DatabaseManager
from views.certificate.certificate_printer import CertificatePrinter


_COL_CERT_REF = 0
_COL_RESULT_DATE = 1
_COL_DESIGNATION = 2
_COL_CLIENT = 3
_COL_INVOICE = 4
_COL_TYPE = 5
_COL_QTE = 6
_COL_QTE_ANALYSEE = 7
_COL_NUM_LOT = 8
_COL_NUM_ACTE = 9
_COL_CLASSE = 10
_COL_DATE_PROD = 11
_COL_DATE_PEREMP = 12
_COL_NUM_PRELEV = 13
_COL_DATE_PV = 14
_COL_DATE_CERT = 15
_COL_ACTIONS = 16
_COL_COUNT = 17

_HEADERS = [
    "N° cert",
    "Date résultat",
    "Désignation",
    "Client",
    "N° facture",
    "Type",
    "Quantité *",
    "Qté Analysée *",
    "N° Lot *",
    "N° Acte",
    "Classe *",
    "Date de production",
    "Date de péremption",
    "Sigle",
    "Date commerce",
    "Date cert *",
    "Actions",
]

CERTIFICATE_REFRESH_INTERVAL_MS = 5000


class OptionalDateEdit(QDateEdit):
    cleared = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDateRange(QDate(1900, 1, 1), QDate(7999, 12, 31))
        self.setDisplayFormat("dd/MM/yyyy")
        self.setSpecialValueText("")
        self.setMinimumWidth(82)
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


class CertificateWorkQueueDialog(QDialog):
    def __init__(self, parent, db_manager):
        super().__init__(parent)
        self.db_manager = db_manager
        self._certificate_types = tuple(self.db_manager.get_certificate_types())
        self._rows: dict[tuple, dict] = {}
        self._printer = CertificatePrinter(self)
        self._refresh_pending = False
        self._is_refreshing = False
        self._last_entries_signature: tuple = ()
        self._show_printed = False
        self._search_text = ""
        self._copied_row_payload: dict | None = None
        self.active_edit_row: tuple | None = None

        self.setWindowTitle("Certificats")
        self.setModal(True)

        self._build_ui()
        self._load_products()
        self._init_refresh_timer()
        self._apply_screen_geometry()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(14, 14, 14, 14)

        title = QLabel("Produits à certifier groupés par date de résultat")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 13px; margin-bottom: 4px;")
        layout.addWidget(title)

        note = QLabel(
            "Affichage par défaut: produits à imprimer. Les produits déjà imprimés restent réimprimables dans la vue dédiée."
        )
        note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet("color: #2F5A8F; font-weight: bold; margin-bottom: 4px;")
        layout.addWidget(note)

        self.refresh_notification = QLabel("")
        self.refresh_notification.setMinimumHeight(30)
        self.refresh_notification.setWordWrap(True)
        self.refresh_notification.setAlignment(Qt.AlignCenter)
        self._clear_refresh_notification()
        layout.addWidget(self.refresh_notification)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filtrer résultat ou type (ex: 12/04, CC)")
        self.search_edit.setMaximumWidth(240)
        self.search_edit.setToolTip("Filtrer par date de résultat ou type de certificat")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        toolbar.addWidget(self.search_edit, 0)
        toolbar.addStretch(1)

        self.toggle_printed_btn = QPushButton("Afficher déjà imprimés")
        self.toggle_printed_btn.setCheckable(True)
        self.toggle_printed_btn.clicked.connect(self._toggle_printed_view)
        toolbar.addWidget(self.toggle_printed_btn)
        layout.addLayout(toolbar)

        self._table = QTableWidget()
        self._table.setColumnCount(_COL_COUNT)
        self._table.setHorizontalHeaderLabels(_HEADERS)
        self._table.setColumnHidden(_COL_RESULT_DATE, True)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.NoSelection)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(48)
        self._table.verticalHeader().setMinimumSectionSize(48)

        hdr = self._table.horizontalHeader()
        hdr.setSectionResizeMode(_COL_CERT_REF, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(_COL_RESULT_DATE, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(_COL_DESIGNATION, QHeaderView.Stretch)
        hdr.setSectionResizeMode(_COL_CLIENT, QHeaderView.Interactive)
        self._table.setColumnWidth(_COL_CLIENT, 82)
        hdr.setSectionResizeMode(_COL_INVOICE, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(_COL_TYPE, QHeaderView.Interactive)
        self._table.setColumnWidth(_COL_TYPE, 260)
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
        self._table.setColumnWidth(_COL_QTE, 68)
        self._table.setColumnWidth(_COL_QTE_ANALYSEE, 72)
        self._table.setColumnWidth(_COL_NUM_LOT, 68)
        self._table.setColumnWidth(_COL_NUM_ACTE, 78)
        self._table.setColumnWidth(_COL_CLASSE, 62)
        self._table.setColumnWidth(_COL_DATE_PROD, 82)
        self._table.setColumnWidth(_COL_DATE_PEREMP, 82)
        self._table.setColumnWidth(_COL_NUM_PRELEV, 62)
        self._table.setColumnWidth(_COL_DATE_PV, 82)
        self._table.setColumnWidth(_COL_DATE_CERT, 82)
        hdr.setSectionResizeMode(_COL_ACTIONS, QHeaderView.Interactive)
        self._table.setColumnWidth(_COL_ACTIONS, 194)
        layout.addWidget(self._table)

    def _apply_screen_geometry(self):
        parent_window = self.parentWidget().window() if self.parentWidget() else None
        screen = parent_window.screen() if parent_window else self.screen()
        if screen is None:
            self.resize(1800, 760)
            return
        available_geometry = screen.availableGeometry()
        target_height = min(max(680, self.sizeHint().height()), available_geometry.height())
        self.setGeometry(
            available_geometry.x(),
            available_geometry.y(),
            available_geometry.width(),
            target_height,
        )

    def _init_refresh_timer(self):
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(CERTIFICATE_REFRESH_INTERVAL_MS)
        self.refresh_notice_timer = QTimer(self)
        self.refresh_notice_timer.setSingleShot(True)
        self.refresh_notice_timer.timeout.connect(self._clear_refresh_notification)

    def _show_refresh_notification(self, message: str):
        self.refresh_notification.setText(message)
        self.refresh_notification.setStyleSheet(
            "background-color: #264b2f; color: white; border: 1px solid #4b8a58; border-radius: 4px; padding: 6px 10px;"
        )
        self.refresh_notice_timer.start(4000)

    def _clear_refresh_notification(self):
        self.refresh_notification.setText("")
        self.refresh_notification.setStyleSheet(
            "background: transparent; color: transparent; border: 1px solid transparent; padding: 6px 10px;"
        )

    @staticmethod
    def _source_key(source: dict) -> tuple:
        invoice_item_id = source.get("invoice_item_id")
        if invoice_item_id is not None:
            return ("item", int(invoice_item_id))
        return ("legacy", source.get("invoice_id"), source.get("invoice_type"), source.get("product_id"))

    def _toggle_printed_view(self, checked: bool):
        self._show_printed = bool(checked)
        self.toggle_printed_btn.setText("Afficher à imprimer" if checked else "Afficher déjà imprimés")
        self._load_products()

    def _on_search_text_changed(self, text: str):
        self._search_text = str(text or "").strip().lower()
        self._load_products()

    @staticmethod
    def _format_iso_date(value: str) -> str:
        text = str(value or "").strip()
        if not text:
            return "Sans date de résultat"
        parsed = QDate.fromString(text, "yyyy-MM-dd")
        if parsed.isValid():
            return parsed.toString("dd/MM/yyyy")
        parsed = QDate.fromString(text, "dd/MM/yyyy")
        if parsed.isValid():
            return parsed.toString("dd/MM/yyyy")
        return text

    def _build_header_data(self, source: dict) -> dict:
        return {
            "company_name": str(source.get("company_name") or "").strip(),
            "responsable": str(source.get("resp") or "").strip(),
            "stat": str(source.get("stat") or "").strip(),
            "nif": str(source.get("nif") or "").strip(),
            "address": str(source.get("address") or "").strip(),
            "date": self._format_iso_date(source.get("date_issue")),
            "date_result": self._format_iso_date(source.get("result_date") or source.get("invoice_date_result")),
            "product_ref": str(source.get("product_ref") or "").strip(),
        }

    def _source_search_values(self, source: dict) -> tuple[str, ...]:
        result_date = str(source.get("result_date") or "").strip()
        active_type = str(source.get("active_certificate_type") or "").strip().upper()
        return (
            result_date.lower(),
            self._format_iso_date(result_date).lower(),
            active_type.lower(),
        )

    def _filter_sources(self, sources: list[dict]) -> list[dict]:
        if not self._search_text:
            return sources
        filtered = []
        for source in sources:
            if any(self._search_text in value for value in self._source_search_values(source) if value):
                filtered.append(source)
        return filtered

    def _fetch_certificate_source_data(self):
        sources = self._filter_sources(self.db_manager.get_certificate_work_queue(include_printed=self._show_printed))
        all_entries = self.db_manager.get_all_standard_certificate_entries()
        allowed_keys = {
            self._source_key(source)
            for source in sources
        }
        saved_entries = {}
        for entry in all_entries:
            key = self._source_key(entry)
            if key not in allowed_keys:
                continue
            saved_entries.setdefault(key, {})[entry.get("certificate_type")] = entry
        return sources, saved_entries

    @staticmethod
    def _payload_signature(payload: dict | None) -> tuple:
        payload = payload or {}
        return tuple(sorted(payload.items()))

    @classmethod
    def _build_entries_signature(cls, sources: list[dict], saved_entries: dict) -> tuple:
        signature = []
        for source in sources:
            key = cls._source_key(source)
            signature.append(
                (
                    key,
                    str(source.get("result_date") or ""),
                    str(source.get("active_certificate_type") or ""),
                    str(source.get("active_num_cert") or ""),
                    str(source.get("printed_at") or ""),
                )
            )
            saved_entries_by_type = saved_entries.get(key, {})
            for cert_type in DatabaseManager.get_certificate_types():
                signature.append((key, cert_type, cls._payload_signature(cls._entry_to_payload(saved_entries_by_type.get(cert_type), {}))))
        return tuple(signature)

    def _load_products(self):
        sources, saved_entries = self._fetch_certificate_source_data()
        self._last_entries_signature = self._build_entries_signature(sources, saved_entries)
        self._rows = {}
        self._table.setRowCount(0)

        if not sources:
            self._table.insertRow(0)
            item = QTableWidgetItem("Aucun produit ne correspond au filtre courant.")
            item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(0, 0, item)
            self._table.setSpan(0, 0, 1, _COL_COUNT)
            return

        groups = {}
        for source in sources:
            raw_key = str(source.get("result_date") or "").strip()
            groups.setdefault(raw_key, {"title": self._format_iso_date(raw_key), "sources": []})["sources"].append(source)

        for raw_key, group_data in groups.items():
            self._insert_group_header(group_data["title"])
            for source in group_data["sources"]:
                self._append_source_row(source, saved_entries.get(self._source_key(source), {}))

    @classmethod
    def _safe_set_stylesheet(cls, widget, stylesheet: str):
        if not cls._widget_is_alive(widget):
            return
        try:
            widget.setStyleSheet(stylesheet)
        except RuntimeError:
            return

    def _row_has_saved_certificate(self, row: dict) -> bool:
        for cert_type in self._certificate_types:
            payload = row["cached_entries"].get(cert_type) or {}
            if str(payload.get("num_cert") or "").strip():
                return True
        return False

    def _apply_saved_row_style(self, row: dict):
        row_index = row.get("table_row")
        if row_index is None:
            return

        is_saved = self._row_has_saved_certificate(row)
        item_bg = QColor("#E8F6EE") if is_saved else QColor("white")
        item_fg = QColor("#134B33") if is_saved else QColor("black")
        input_style = (
            "QLineEdit, QDateEdit { background-color: #F4FFF8; color: #134B33; border: 2px solid #2E8B57; border-radius: 3px; }"
            if is_saved
            else ""
        )
        button_style = (
            "QPushButton { background-color: #DDF3E5; color: #134B33; border: 2px solid #2E8B57; border-radius: 4px; font-weight: 600; }"
            if is_saved
            else ""
        )
        preview_button_style = (
            "QPushButton { background-color: #DDF3E5; color: #134B33; border: none; border-radius: 4px; font-weight: 600; }"
            if is_saved
            else "QPushButton { border: none; }"
        )

        for col in (_COL_CERT_REF, _COL_RESULT_DATE, _COL_DESIGNATION, _COL_CLIENT, _COL_INVOICE):
            item = self._table.item(row_index, col)
            if item is not None:
                item.setBackground(item_bg)
                item.setForeground(item_fg)

        for widget_name in (
            "qty_edit",
            "qty_analysee_edit",
            "num_lot_edit",
            "num_acte_edit",
            "classe_edit",
            "date_prod_edit",
            "date_peremp_edit",
            "num_prelev_edit",
            "date_pv_edit",
            "date_cert_edit",
        ):
            self._safe_set_stylesheet(row.get(widget_name), input_style)

        for widget_name in ("btn_copy", "btn_paste", "btn_save"):
            self._safe_set_stylesheet(row.get(widget_name), button_style)
        self._safe_set_stylesheet(row.get("btn_print"), preview_button_style)
    def _insert_group_header(self, title: str):
        row = self._table.rowCount()
        self._table.insertRow(row)
        item = QTableWidgetItem(f"Date de résultat: {title}")
        item.setFlags(Qt.ItemIsEnabled)
        item.setBackground(Qt.darkBlue)
        item.setForeground(Qt.white)
        self._table.setItem(row, 0, item)
        self._table.setSpan(row, 0, 1, _COL_COUNT)

    def _insert_divider_row(self, title: str):
        row = self._table.rowCount()
        self._table.insertRow(row)
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 4, 8, 4)
        label = QLabel(title)
        label.setStyleSheet("color: #2F5A8F; font-weight: bold;")
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: #7B95B6;")
        layout.addWidget(label)
        layout.addWidget(line, 1)
        self._table.setCellWidget(row, 0, container)
        self._table.setSpan(row, 0, 1, _COL_COUNT)

    def _append_source_row(self, source: dict, saved_entries: dict):
        row_index = self._table.rowCount()
        self._table.insertRow(row_index)
        key = self._source_key(source)
        base_defaults = {
            "num_act": str(source.get("line_num_act") or "").strip(),
            "ref_b_analyse": source.get("ref_b_analyse"),
        }

        cert_item = QTableWidgetItem("-/-")
        cert_item.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row_index, _COL_CERT_REF, cert_item)

        result_item = QTableWidgetItem(self._format_iso_date(source.get("result_date")))
        result_item.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row_index, _COL_RESULT_DATE, result_item)

        designation_item = QTableWidgetItem(str(source.get("product_name") or ""))
        designation_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._table.setItem(row_index, _COL_DESIGNATION, designation_item)

        client_item = QTableWidgetItem(str(source.get("company_name") or ""))
        self._table.setItem(row_index, _COL_CLIENT, client_item)

        invoice_item = QTableWidgetItem(str(source.get("invoice_id") or ""))
        invoice_item.setTextAlignment(Qt.AlignCenter)
        self._table.setItem(row_index, _COL_INVOICE, invoice_item)

        qty_edit = self._make_line_edit("Qté", 66)
        qty_analysee_edit = self._make_line_edit("Qté A.", 70)
        num_lot_edit = self._make_line_edit("Lot", 66)
        num_acte_edit = self._make_line_edit("Acte", 78)
        num_acte_edit.setText(base_defaults.get("num_act", ""))
        classe_edit = self._make_line_edit("Classe", 62)
        date_prod_edit = self._make_date_edit()
        date_peremp_edit = self._make_date_edit()
        num_prelev_edit = self._make_line_edit("Sigle", 62)
        date_pv_edit = self._make_date_edit()
        date_cert_edit = self._make_date_edit()

        self._table.setCellWidget(row_index, _COL_QTE, qty_edit)
        self._table.setCellWidget(row_index, _COL_QTE_ANALYSEE, qty_analysee_edit)
        self._table.setCellWidget(row_index, _COL_NUM_LOT, num_lot_edit)
        self._table.setCellWidget(row_index, _COL_NUM_ACTE, num_acte_edit)
        self._table.setCellWidget(row_index, _COL_CLASSE, classe_edit)
        self._table.setCellWidget(row_index, _COL_DATE_PROD, date_prod_edit)
        self._table.setCellWidget(row_index, _COL_DATE_PEREMP, date_peremp_edit)
        self._table.setCellWidget(row_index, _COL_NUM_PRELEV, num_prelev_edit)
        self._table.setCellWidget(row_index, _COL_DATE_PV, date_pv_edit)
        self._table.setCellWidget(row_index, _COL_DATE_CERT, date_cert_edit)

        type_container, type_group, type_checkboxes = self._make_type_selector(key)
        check_icon = resolve_resource_path("images/checkbox-check-white.svg").as_posix()
        checkbox_style = (
            "QCheckBox::indicator { width: 16px; height: 16px; border: 1px solid white; background: transparent; }"
            f"QCheckBox::indicator:checked {{ image: url({check_icon}); border: 1px solid white; background: transparent; }}"
        )
        for cert_type, checkbox in type_checkboxes.items():
            checkbox.setStyleSheet(checkbox_style)
            checkbox.toggled.connect(
                lambda checked, current_key=key, selected_type=cert_type: checked and self._on_certificate_type_selected(current_key, selected_type)
            )
        self._table.setCellWidget(row_index, _COL_TYPE, type_container)

        action_container = QWidget()
        action_layout = QHBoxLayout(action_container)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(0)
        btn_copy = QPushButton("Copier")
        btn_paste = QPushButton("Coller")
        btn_save = QPushButton("Modifier")
        btn_save.setObjectName("certificateEditButton")
        btn_print = QPushButton("Aperçu")
        btn_print.setObjectName("certificatePrintButton")
        button_width = 86
        button_height = 24
        for action_button in (btn_copy, btn_paste, btn_save, btn_print):
            action_button.setMinimumWidth(button_width)
            action_button.setMaximumWidth(button_width)
            action_button.setMinimumHeight(button_height)
            action_button.setMaximumHeight(button_height)
        action_container.setMinimumWidth((button_width * 2) + 8)
        btn_copy.setToolTip("Copier la ligne")
        btn_paste.setToolTip("Coller sur la ligne")
        btn_save.setToolTip("Modifier la ligne")
        btn_print.setToolTip("Aperçu du certificat")
        btn_copy.clicked.connect(lambda _, current_key=key: self._on_row_copy_clicked(current_key))
        btn_paste.clicked.connect(lambda _, current_key=key: self._on_row_paste_clicked(current_key))
        btn_save.clicked.connect(lambda _, current_key=key: self._on_row_edit_clicked(current_key))
        btn_print.clicked.connect(lambda _, current_key=key: self._on_row_print_clicked(current_key))
        action_grid = QVBoxLayout()
        action_grid.setContentsMargins(0, 0, 0, 0)
        action_grid.setSpacing(2)
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(2)
        top_row.addWidget(btn_copy)
        top_row.addWidget(btn_paste)
        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(2)
        bottom_row.addWidget(btn_save)
        bottom_row.addWidget(btn_print)
        action_grid.addLayout(top_row)
        action_grid.addLayout(bottom_row)
        action_layout.addLayout(action_grid)
        self._table.setCellWidget(row_index, _COL_ACTIONS, action_container)
        self._table.setRowHeight(row_index, 56)

        row_data = {
            "key": key,
            "table_row": row_index,
            "invoice_item_id": source.get("invoice_item_id"),
            "invoice_id": source.get("invoice_id"),
            "invoice_type": source.get("invoice_type") or "standard",
            "pid": source.get("product_id"),
            "name": str(source.get("product_name") or ""),
            "company_name": str(source.get("company_name") or ""),
            "result_date": str(source.get("result_date") or "").strip(),
            "display_result_date": self._format_iso_date(source.get("result_date")),
            "header_data": self._build_header_data(source),
            "printed_at": source.get("printed_at"),
            "type_group": type_group,
            "type_checkboxes": type_checkboxes,
            "qty_edit": qty_edit,
            "qty_analysee_edit": qty_analysee_edit,
            "num_lot_edit": num_lot_edit,
            "num_acte_edit": num_acte_edit,
            "classe_edit": classe_edit,
            "date_prod_edit": date_prod_edit,
            "date_peremp_edit": date_peremp_edit,
            "num_prelev_edit": num_prelev_edit,
            "date_pv_edit": date_pv_edit,
            "date_cert_edit": date_cert_edit,
            "btn_copy": btn_copy,
            "btn_paste": btn_paste,
            "btn_save": btn_save,
            "btn_print": btn_print,
            "cert_ref_item": cert_item,
            "ref_b_analyse": base_defaults.get("ref_b_analyse"),
            "base_defaults": dict(base_defaults),
            "cached_entries": {
                cert_type: self._entry_to_payload(saved_entries.get(cert_type), base_defaults)
                for cert_type in self._certificate_types
            },
            "active_cert_type": None,
            "persisted_cert_type": None,
            "is_editing": False,
            "loading": False,
        }
        self._rows[key] = row_data

        for widget in (
            qty_edit,
            qty_analysee_edit,
            num_lot_edit,
            num_acte_edit,
            classe_edit,
            num_prelev_edit,
        ):
            widget.editingFinished.connect(lambda current_key=key: self._on_row_data_changed(current_key))
        date_prod_edit.dateChanged.connect(lambda _date, current_key=key, edit=date_prod_edit: self._on_date_edit_changed(current_key, edit))
        date_peremp_edit.dateChanged.connect(lambda _date, current_key=key, edit=date_peremp_edit: self._on_date_edit_changed(current_key, edit))
        date_pv_edit.dateChanged.connect(lambda _date, current_key=key, edit=date_pv_edit: self._on_date_edit_changed(current_key, edit))
        date_cert_edit.dateChanged.connect(lambda _date, current_key=key, edit=date_cert_edit: self._on_date_edit_changed(current_key, edit))
        date_prod_edit.cleared.connect(lambda current_key=key: self._on_row_data_changed(current_key))
        date_peremp_edit.cleared.connect(lambda current_key=key: self._on_row_data_changed(current_key))
        date_pv_edit.cleared.connect(lambda current_key=key: self._on_row_data_changed(current_key))
        date_cert_edit.cleared.connect(lambda current_key=key: self._on_row_data_changed(current_key))

        initial_type = str(source.get("active_certificate_type") or "").strip().upper() or None
        if initial_type not in self._certificate_types:
            initial_type = next((cert_type for cert_type in self._certificate_types if saved_entries.get(cert_type)), None)
        if initial_type:
            blockers = [QSignalBlocker(checkbox) for checkbox in type_checkboxes.values()]
            try:
                type_checkboxes[initial_type].setChecked(True)
            finally:
                del blockers
            row_data["active_cert_type"] = initial_type
            row_data["persisted_cert_type"] = initial_type
            self._load_row_values(row_data, row_data["cached_entries"].get(initial_type) or self._default_entry_to_payload(base_defaults))
        self._set_row_inputs_read_only(row_data, True)
        self._set_row_action_state(row_data)

    def _make_type_selector(self, row_key: tuple):
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignCenter)
        group = QButtonGroup(container)
        group.setExclusive(True)
        checkboxes = {}
        for cert_type in self._certificate_types:
            wrapper = QWidget()
            wrapper_layout = QVBoxLayout(wrapper)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)
            wrapper_layout.setSpacing(1)
            wrapper_layout.setAlignment(Qt.AlignCenter)
            label = QLabel(cert_type)
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 10px; font-weight: 600;")
            checkbox = QCheckBox()
            checkbox.setEnabled(False)
            checkboxes[cert_type] = checkbox
            group.addButton(checkbox)
            wrapper_layout.addWidget(label)
            wrapper_layout.addWidget(checkbox)
            layout.addWidget(wrapper)
        return container, group, checkboxes

    @staticmethod
    def _make_date_edit() -> OptionalDateEdit:
        edit = OptionalDateEdit()
        edit.setMinimumWidth(82)
        edit.setMaximumWidth(82)
        edit.setReadOnly(True)
        return edit

    @staticmethod
    def _widget_is_alive(widget) -> bool:
        if widget is None:
            return False
        try:
            widget.objectName()
            return True
        except RuntimeError:
            return False

    @classmethod
    def _safe_has_focus(cls, widget) -> bool:
        if not cls._widget_is_alive(widget):
            return False
        try:
            return widget.hasFocus()
        except RuntimeError:
            return False

    @classmethod
    def _safe_set_enabled(cls, widget, enabled: bool):
        if not cls._widget_is_alive(widget):
            return
        try:
            widget.setEnabled(enabled)
        except RuntimeError:
            return

    @classmethod
    def _safe_set_tooltip(cls, widget, text: str):
        if not cls._widget_is_alive(widget):
            return
        try:
            widget.setToolTip(text)
        except RuntimeError:
            return

    def _get_row(self, row_key: tuple):
        return self._rows.get(row_key)

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
        edit.setMinimumWidth(width)
        edit.setMaximumWidth(width)
        edit.setReadOnly(True)
        return edit

    @staticmethod
    def _editable_widgets(row: dict):
        return (
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
        )

    def _set_row_inputs_read_only(self, row: dict, read_only: bool):
        for widget in self._editable_widgets(row):
            if isinstance(widget, QLineEdit):
                widget.setReadOnly(read_only)
                continue
            widget.setReadOnly(read_only)
            line_edit = widget.lineEdit()
            if line_edit is not None:
                line_edit.setReadOnly(read_only)
        for checkbox in row.get("type_checkboxes", {}).values():
            self._safe_set_enabled(checkbox, not read_only)

    def _enter_row_edit_mode(self, row: dict):
        if self.active_edit_row is not None and self.active_edit_row != row["key"]:
            return False
        self.active_edit_row = row["key"]
        row["is_editing"] = True
        self._set_row_inputs_read_only(row, False)
        row["qty_edit"].setFocus()
        self._set_row_action_state(row)
        return True

    def _exit_row_edit_mode(self, row: dict):
        if self.active_edit_row == row["key"]:
            self.active_edit_row = None
        row["is_editing"] = False
        self._set_row_inputs_read_only(row, True)
        self._set_row_action_state(row)

    @classmethod
    def _default_entry_to_payload(cls, base_defaults: dict | None = None) -> dict:
        payload = cls._entry_to_payload(None, base_defaults)
        payload["date_cert"] = QDate.currentDate().toString("dd/MM/yyyy")
        payload["date_cert_modified"] = True
        payload["printed_at"] = ""
        return payload

    @staticmethod
    def _entry_to_payload(entry: dict | None, base_defaults: dict | None = None) -> dict:
        base_defaults = base_defaults or {}
        date_production, date_production_modified = CertificateWorkQueueDialog._extract_date_payload(entry, "date_production", "date_production_modified")
        date_peremption, date_peremption_modified = CertificateWorkQueueDialog._extract_date_payload(entry, "date_peremption", "date_peremption_modified")
        date_commerce, date_commerce_modified = CertificateWorkQueueDialog._extract_date_payload(entry, "date_commerce", "date_commerce_modified")
        date_cert, date_cert_modified = CertificateWorkQueueDialog._extract_date_payload(entry, "date_cert", "date_cert_modified")
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
            "printed_at": str((entry or {}).get("printed_at") or "").strip(),
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
                edit.setDate(CertificateWorkQueueDialog._parse_date_value(text))
                edit.setProperty("user_modified", True)
            else:
                if isinstance(edit, OptionalDateEdit):
                    edit._set_empty_state()
                else:
                    edit.setDate(edit.minimumDate())
                edit.setProperty("user_modified", False)
        finally:
            edit.setProperty("loading_value", False)

    def _on_date_edit_changed(self, row_key: tuple, edit: QDateEdit):
        if bool(edit.property("loading_value")):
            return
        edit.setProperty("user_modified", True)
        self._on_row_data_changed(row_key)

    def _load_row_values(self, row: dict, payload: dict):
        row["loading"] = True
        try:
            row["qty_edit"].setText(payload.get("quantity", ""))
            row["qty_analysee_edit"].setText(payload.get("quantity_analysee", ""))
            row["num_lot_edit"].setText(payload.get("num_lot", ""))
            row["num_acte_edit"].setText(payload.get("num_act", ""))
            row["classe_edit"].setText(payload.get("classe", ""))
            self._set_date_edit_state(row["date_prod_edit"], payload.get("date_production", ""), payload.get("date_production_modified", False))
            self._set_date_edit_state(row["date_peremp_edit"], payload.get("date_peremption", ""), payload.get("date_peremption_modified", False))
            row["num_prelev_edit"].setText(payload.get("num_prl", ""))
            self._set_date_edit_state(row["date_pv_edit"], payload.get("date_commerce", ""), payload.get("date_commerce_modified", False))
            self._set_date_edit_state(row["date_cert_edit"], payload.get("date_cert", ""), payload.get("date_cert_modified", False))
        finally:
            row["loading"] = False

    def _row_has_focus(self, row: dict) -> bool:
        widgets = [*self._editable_widgets(row), *row.get("type_checkboxes", {}).values()]
        return any(self._safe_has_focus(widget) for widget in widgets)

    def _row_is_being_edited(self, row: dict) -> bool:
        return bool(row.get("loading")) or self._row_has_focus(row)

    def _row_has_pending_input(self, row: dict) -> bool:
        text_widgets = (
            row["qty_edit"],
            row["qty_analysee_edit"],
            row["num_lot_edit"],
            row["num_acte_edit"],
            row["classe_edit"],
            row["num_prelev_edit"],
        )
        if any(widget.text().strip() for widget in text_widgets):
            return True
        date_widgets = (
            row["date_prod_edit"],
            row["date_peremp_edit"],
            row["date_pv_edit"],
            row["date_cert_edit"],
        )
        return any(bool(widget.property("user_modified")) for widget in date_widgets)

    def _persist_editing_rows_on_close(self):
        for row in self._rows.values():
            if not row.get("is_editing"):
                continue

            cert_type = self._selected_certificate_type(row)
            if cert_type is None:
                if self._row_has_pending_input(row):
                    raise RuntimeError(
                        f"Veuillez sélectionner un type de certificat pour « {row['name']} » avant de fermer afin d'enregistrer les données saisies."
                    )
                self._exit_row_edit_mode(row)
                continue

            row["cached_entries"][cert_type] = self._snapshot_row_values(row, cert_type)
            self._persist_row_state(row, cert_type)
            self._exit_row_edit_mode(row)

    def refresh_certificate_entries_silently(self):
        if not self.isVisible() or self._is_refreshing:
            return
        try:
            sources, saved_entries = self._fetch_certificate_source_data()
        except Exception:
            return
        latest_signature = self._build_entries_signature(sources, saved_entries)
        if latest_signature == self._last_entries_signature:
            return
        if any(self._row_is_being_edited(row) for row in self._rows.values()):
            self._refresh_pending = True
            return
        self._is_refreshing = True
        try:
            self._load_products()
            self._refresh_pending = False
            self._show_refresh_notification("Les certificats ont été mis à jour automatiquement.")
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
            "printed_at": str(current_payload.get("printed_at") or row.get("printed_at") or "").strip(),
        }

    def _persist_row_state(self, row: dict, cert_type: str | None = None):
        current_type = cert_type or row.get("active_cert_type")
        if not current_type:
            return
        payload = row["cached_entries"].get(current_type) or self._snapshot_row_values(row)
        self.db_manager.save_certificate_entry(
            row["invoice_id"],
            row["invoice_type"],
            row["pid"],
            current_type,
            payload,
            invoice_item_id=row.get("invoice_item_id"),
        )
        self.db_manager.replace_certificate_entry_type(
            row["invoice_id"],
            row["invoice_type"],
            row["pid"],
            current_type,
            invoice_item_id=row.get("invoice_item_id"),
        )
        row["printed_at"] = payload.get("printed_at")
        row["persisted_cert_type"] = current_type
        for other_type in self._certificate_types:
            if other_type == current_type:
                continue
            other_payload = dict(row["cached_entries"].get(other_type) or self._default_entry_to_payload(row.get("base_defaults")))
            other_payload["num_cert"] = ""
            other_payload["printed_at"] = ""
            row["cached_entries"][other_type] = other_payload
        self._last_entries_signature = ()

    def _reset_certificate_cache(self, row: dict, cert_type: str):
        row["cached_entries"][cert_type] = self._default_entry_to_payload(row.get("base_defaults"))

    def _restore_certificate_type_selection(self, row: dict, cert_type: str, payload: dict):
        blockers = [QSignalBlocker(checkbox) for checkbox in row.get("type_checkboxes", {}).values()]
        try:
            checkbox = row.get("type_checkboxes", {}).get(cert_type)
            if checkbox is not None:
                checkbox.setChecked(True)
        finally:
            del blockers
        row["active_cert_type"] = cert_type
        row["persisted_cert_type"] = cert_type
        row["cached_entries"][cert_type] = payload
        self._load_row_values(row, payload)
        self._set_row_action_state(row)

    def _switch_numbered_certificate_type(self, row: dict, source_type: str, target_type: str) -> bool:
        source_payload = self._snapshot_row_values(row, source_type)
        row["cached_entries"][source_type] = source_payload
        try:
            migrated_payload = self.db_manager.switch_certificate_entry_type(
                row["invoice_id"],
                row["invoice_type"],
                row["pid"],
                source_type,
                target_type,
                source_payload,
                invoice_item_id=row.get("invoice_item_id"),
            )
        except Exception as exc:
            self._restore_certificate_type_selection(row, source_type, source_payload)
            QMessageBox.critical(
                self,
                "Changement de type impossible",
                f"Le certificat « {row['name']} » n'a pas pu être basculé de {source_type} vers {target_type}.\n\n{exc}",
            )
            return False
        migrated_payload["printed_at"] = ""
        self._reset_certificate_cache(row, source_type)
        row["active_cert_type"] = target_type
        row["persisted_cert_type"] = target_type
        row["cached_entries"][target_type] = migrated_payload
        row["printed_at"] = ""
        self._load_row_values(row, migrated_payload)
        self._last_entries_signature = ()
        self._set_row_action_state(row)
        return True

    def _on_certificate_type_selected(self, row_key: tuple, cert_type: str):
        row = self._get_row(row_key)
        if row is None:
            return
        previous_type = row.get("active_cert_type")
        if previous_type and previous_type != cert_type:
            row["cached_entries"][previous_type] = self._snapshot_row_values(row, previous_type)
        row["active_cert_type"] = cert_type
        payload = row["cached_entries"].get(cert_type) or self._default_entry_to_payload({"num_act": row["num_acte_edit"].text().strip()})
        self._load_row_values(row, payload)
        row["cached_entries"][cert_type] = self._snapshot_row_values(row, cert_type)
        self._set_row_action_state(row)

    def _on_row_data_changed(self, row_key: tuple):
        row = self._get_row(row_key)
        if row is None:
            return
        if row.get("loading"):
            return
        if not row.get("is_editing"):
            return
        cert_type = row.get("active_cert_type")
        if not cert_type:
            return
        row["cached_entries"][cert_type] = self._snapshot_row_values(row, cert_type)
        self._set_row_action_state(row)

    def _update_cert_ref_item(self, row: dict):
        cert_type = row.get("active_cert_type")
        payload = row["cached_entries"].get(cert_type or "", {}) if cert_type else {}
        num_cert = str(payload.get("num_cert") or "").strip()
        if cert_type and num_cert:
            row["cert_ref_item"].setText(f"{num_cert}/{cert_type}")
        else:
            row["cert_ref_item"].setText("-/-")
        row["cert_ref_item"].setTextAlignment(Qt.AlignCenter)

    def _set_row_action_state(self, row: dict):
        cert_type = row.get("active_cert_type")
        has_number = bool(cert_type and str((row["cached_entries"].get(cert_type) or {}).get("num_cert") or "").strip())
        self._safe_set_enabled(row.get("btn_copy"), True)
        self._safe_set_enabled(row.get("btn_paste"), self._copied_row_payload is not None)
        self._safe_set_enabled(row.get("btn_save"), True)
        self._safe_set_enabled(row.get("btn_print"), has_number and not row.get("is_editing"))
        row.get("btn_save").setText("Sauver" if row.get("is_editing") else "Modifier")
        self._update_cert_ref_item(row)
        self._apply_saved_row_style(row)
        if row.get("is_editing"):
            self._safe_set_tooltip(row.get("btn_save"), "Sauver les modifications de la ligne certificat.")
            self._safe_set_tooltip(row.get("btn_print"), "Terminez par Sauver avant d'ouvrir l'aperçu.")
            return
        self._safe_set_tooltip(row.get("btn_save"), "Déverrouiller la ligne pour modification.")
        if cert_type is None:
            self._safe_set_tooltip(row.get("btn_print"), "Enregistrez d'abord un certificat pour pouvoir l'ouvrir en aperçu.")
            return
        if has_number:
            num_cert = str((row["cached_entries"].get(cert_type) or {}).get("num_cert") or "").strip()
            self._safe_set_tooltip(row.get("btn_print"), f"Aperçu du certificat {cert_type} n° {num_cert}.")
            return
        self._safe_set_tooltip(row.get("btn_print"), "Enregistrez d'abord le certificat pour attribuer son numéro avant aperçu.")

    def _confirm_certificate_number_lock(self, row: dict, cert_type: str) -> bool:
        reply = QMessageBox.question(
            self,
            "Enregistrer le certificat",
            (
                f"Voulez-vous vraiment enregistrer le certificat {cert_type} pour « {row['name']} » ?\n\n"
                "Le N° certificat sera attribué automatiquement. Si vous changez plus tard de type, "
                "la numérotation sera réajustée automatiquement pour garder une suite cohérente."
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _save_row_certificate(self, row_key: tuple, require_confirmation: bool = True, show_success: bool = True) -> bool:
        row = self._get_row(row_key)
        if row is None:
            return False
        cert_type = self._selected_certificate_type(row)
        if cert_type is None:
            QMessageBox.warning(self, "Type manquant", f"Veuillez sélectionner un type de certificat pour « {row['name']} ».")
            return False
        if not self._validate_required_fields(row_key):
            return False
        payload = self._snapshot_row_values(row, cert_type)
        previous_type = row.get("persisted_cert_type")
        previous_payload = row["cached_entries"].get(previous_type, {}) if previous_type else {}

        if previous_type and previous_type != cert_type and str(previous_payload.get("num_cert") or "").strip():
            if require_confirmation and not self._confirm_certificate_number_lock(row, cert_type):
                return False
            if not self._switch_numbered_certificate_type(row, previous_type, cert_type):
                return False
            payload = row["cached_entries"].get(cert_type) or payload
        else:
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

    def _on_row_edit_clicked(self, row_key: tuple):
        row = self._get_row(row_key)
        if row is None:
            return
        if not row.get("is_editing"):
            self._enter_row_edit_mode(row)
            return
        if not self._save_row_certificate(row_key, require_confirmation=True, show_success=True):
            return
        self._exit_row_edit_mode(row)
        self._load_products()
        self._show_refresh_notification("Certificat sauvegardé.")

    def _copyable_row_payload(self, row_key: tuple):
        row = self._get_row(row_key)
        if row is None:
            return None
        payload = self._snapshot_row_values(row)
        return {
            "quantity": payload.get("quantity", ""),
            "quantity_analysee": payload.get("quantity_analysee", ""),
            "num_lot": payload.get("num_lot", ""),
            "num_act": payload.get("num_act", ""),
            "classe": payload.get("classe", ""),
            "date_production": payload.get("date_production", ""),
            "date_production_modified": payload.get("date_production_modified", False),
            "date_peremption": payload.get("date_peremption", ""),
            "date_peremption_modified": payload.get("date_peremption_modified", False),
            "num_prl": payload.get("num_prl", ""),
            "date_commerce": payload.get("date_commerce", ""),
            "date_commerce_modified": payload.get("date_commerce_modified", False),
            "date_cert": payload.get("date_cert", ""),
            "date_cert_modified": payload.get("date_cert_modified", False),
        }

    def _on_row_copy_clicked(self, row_key: tuple):
        self._copied_row_payload = self._copyable_row_payload(row_key)
        for row_data in self._rows.values():
            self._set_row_action_state(row_data)
        self._show_refresh_notification("La ligne certificat a été copiée.")

    def _on_row_paste_clicked(self, row_key: tuple):
        if not self._copied_row_payload:
            QMessageBox.information(self, "Coller", "Aucune ligne copiée.")
            return
        row = self._get_row(row_key)
        if row is None:
            return
        cert_type = row.get("active_cert_type")
        for current_type in self._certificate_types:
            current_payload = dict(row["cached_entries"].get(current_type) or self._default_entry_to_payload(row.get("base_defaults")))
            current_payload.update(self._copied_row_payload)
            current_payload["num_cert"] = str((row["cached_entries"].get(current_type) or {}).get("num_cert") or "")
            current_payload["printed_at"] = str((row["cached_entries"].get(current_type) or {}).get("printed_at") or "")
            row["cached_entries"][current_type] = current_payload

        visible_payload = row["cached_entries"].get(cert_type) if cert_type else dict(self._copied_row_payload)
        self._load_row_values(row, visible_payload)
        if cert_type and row.get("is_editing"):
            self._on_row_data_changed(row_key)
        else:
            self._set_row_action_state(row)

    def _row_extras(self, row_key: tuple) -> dict:
        row = self._get_row(row_key)
        if row is None:
            return {}
        payload = self._snapshot_row_values(row)
        return {
            "quantite": payload["quantity"],
            "quantite_analysee": payload["quantity_analysee"],
            "num_lot": payload["num_lot"],
            "num_acte": payload["num_act"],
            "num_cert": payload["num_cert"],
            "classe": payload["classe"],
            "date_production": payload["date_production"],
            "date_peremption": payload["date_peremption"],
            "num_prl": payload["num_prl"],
            "date_commerce": payload["date_commerce"],
            "date_cert": payload["date_cert"],
            "ref_b_analyse": row.get("ref_b_analyse") or "",
            "invoice_number": row.get("invoice_id") or "",
            "analyse": self._build_analyse_text(row["pid"]),
        }

    def _validate_required_fields(self, row_key: tuple) -> bool:
        row = self._get_row(row_key)
        if row is None:
            return False
        required_fields = [
            ("Quantité", row["qty_edit"].text().strip(), row["qty_edit"]),
            ("Qté Analysée", row["qty_analysee_edit"].text().strip(), row["qty_analysee_edit"]),
            ("N° Lot", row["num_lot_edit"].text().strip(), row["num_lot_edit"]),
            ("Classe", row["classe_edit"].text().strip(), row["classe_edit"]),
            ("Date cert", self._date_edit_value(row["date_cert_edit"]), row["date_cert_edit"]),
        ]
        for label, value, widget in required_fields:
            if value:
                continue
            QMessageBox.warning(self, "Champ obligatoire", f"Le champ « {label} » est obligatoire pour « {row['name']} ».")
            widget.setFocus()
            return False
        return True

    def _build_analyse_text(self, pid) -> str:
        product = self.db_manager.get_product_by_id(pid) or {}
        analyses = []
        if self._to_float(product.get("physico", 0)) > 0:
            analyses.append("Physico-chimique")
        if self._to_float(product.get("micro", 0)) > 0:
            analyses.append("Microbiologique")
        if self._to_float(product.get("toxico", 0)) > 0:
            analyses.append("Toxicologique")
        return ", ".join(analyses)

    @staticmethod
    def _to_float(value) -> float:
        text = str(value or "").replace(" ", "").replace("Ar", "").strip()
        try:
            return float(text) if text else 0.0
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _selected_certificate_type(row: dict) -> str | None:
        for cert_type, checkbox in row.get("type_checkboxes", {}).items():
            if checkbox.isChecked():
                return cert_type
        return None

    @staticmethod
    def _current_printed_timestamp() -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _mark_row_as_printed(self, row: dict, cert_type: str):
        payload = dict(row["cached_entries"].get(cert_type) or self._snapshot_row_values(row, cert_type))
        payload["printed_at"] = self._current_printed_timestamp()
        row["cached_entries"][cert_type] = payload
        row["printed_at"] = payload["printed_at"]
        self._persist_row_state(row, cert_type)
        self._load_products()

    def _on_row_print_clicked(self, row_key: tuple):
        row = self._get_row(row_key)
        if row is None:
            return
        if row.get("is_editing"):
            QMessageBox.information(self, "Sauvegarde requise", f"Veuillez d'abord sauver la ligne de « {row['name']} » avant l'aperçu.")
            return
        cert_type = self._selected_certificate_type(row)
        if cert_type is None:
            QMessageBox.warning(self, "Type manquant", f"Veuillez sélectionner un type de certificat pour « {row['name']} ».")
            return
        payload = row["cached_entries"].get(cert_type) or {}
        if not str(payload.get("num_cert") or "").strip():
            QMessageBox.warning(
                self,
                "Certificat non enregistré",
                f"Veuillez d'abord enregistrer le certificat {cert_type} pour « {row['name']} » afin d'attribuer le N° certificat.",
            )
            return
        success = self._printer.preview_certificates(
            row["header_data"],
            [(row["pid"], row["name"], cert_type, self._row_extras(row_key))],
        )
        if not success:
            return
        try:
            self._mark_row_as_printed(row, cert_type)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Statut d'impression indisponible",
                f"L'aperçu du certificat pour « {row['name']} » a réussi, mais son statut imprimé n'a pas pu être enregistré.\n\n{exc}",
            )

    def closeEvent(self, event):
        try:
            self._persist_editing_rows_on_close()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Enregistrement impossible",
                f"Les données du formulaire certificat n'ont pas pu être enregistrées avant la fermeture.\n\n{exc}",
            )
            event.ignore()
            return
        if hasattr(self, "refresh_timer"):
            self.refresh_timer.stop()
        if hasattr(self, "refresh_notice_timer"):
            self.refresh_notice_timer.stop()
        super().closeEvent(event)
