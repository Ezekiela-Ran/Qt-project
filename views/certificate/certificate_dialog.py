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
from PySide6.QtGui import QColor

from views.certificate.certificate_printer import CertificatePrinter

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
    "Quantité",
    "Qté Analysée",
    "N° Lot",
    "N° Acte",
    "N° Cert",
    "Classe",
    "Date Prod.",
    "Date Péremp.",
    "N° Prélèvement",
    "Date PV",
    "CC",
    "CNC",
    "Imprimer",
]

_GREEN = "#c8f7c5"


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

    def __init__(self, parent, form, selected_products, db_manager, product_manager=None):
        super().__init__(parent)
        self.form = form
        self.selected_products = selected_products
        self.db_manager = db_manager
        self.product_manager = product_manager
        self._rows: list[dict] = []
        self._printed_pids: set = set()

        self.setWindowTitle("Certificats — CC / CNC")
        self.setMinimumSize(1200, 420)
        self.setModal(True)

        self._build_ui()
        self._load_products()

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
            self._table.setColumnWidth(col, 110)
        hdr.setSectionResizeMode(_COL_CC, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(_COL_CNC, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(_COL_IMPRIMER, QHeaderView.ResizeToContents)

        layout.addWidget(self._table)

    def _load_products(self):
        self._table.setRowCount(len(self.selected_products))
        for i, pid in enumerate(self.selected_products):
            product = self.db_manager.get_product_by_id(pid)
            name = product["product_name"] if product else f"Produit {pid}"
            num_acte = ""
            if self.product_manager:
                num_acte = self.product_manager.selected_num_acts.get(pid, "") or ""
            self._add_row(i, pid, name, num_acte)

    def _add_row(self, row_index: int, pid, name: str, num_acte: str = ""):
        """Ajoute une ligne avec champs de saisie et boutons CC / CNC / Imprimer."""
        item = QTableWidgetItem(name)
        item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        self._table.setItem(row_index, _COL_DESIGNATION, item)

        qty_edit         = QLineEdit(); qty_edit.setPlaceholderText("ex: 10 kg")
        qty_analysee_edit = QLineEdit(); qty_analysee_edit.setPlaceholderText("ex: 10 kg")
        num_lot_edit     = QLineEdit(); num_lot_edit.setPlaceholderText("N° Lot")
        num_acte_edit    = QLineEdit(num_acte); num_acte_edit.setPlaceholderText("N° Acte")
        num_cert_edit    = QLineEdit(); num_cert_edit.setPlaceholderText("N° Cert")
        classe_edit      = QLineEdit(); classe_edit.setPlaceholderText("Classe")
        date_prod_edit   = self._make_date_edit()
        date_peremp_edit = self._make_date_edit()
        num_prelev_edit  = QLineEdit(); num_prelev_edit.setPlaceholderText("N° Prélèvement")
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
        _wire_exclusive(actual_cc, actual_cnc)
        self._table.setCellWidget(row_index, _COL_CC,  cc_container)
        self._table.setCellWidget(row_index, _COL_CNC, cnc_container)

        btn_print = QPushButton("Imprimer")
        btn_print.setObjectName("certificatePrintButton")
        self._table.setCellWidget(row_index, _COL_IMPRIMER, btn_print)
        btn_print.clicked.connect(lambda _, r=row_index: self._on_row_print_clicked(r))

        self._rows.append({
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
        })

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
        edit.setDisplayFormat("dd/MM/yyyy")
        edit.setDate(QDate.currentDate())
        return edit

    # ------------------------------------------------------------------
    # Logique d'impression par ligne
    # ------------------------------------------------------------------

    def _row_extras(self, row_index: int) -> dict:
        r = self._rows[row_index]
        return {
            "quantite":          r["qty_edit"].text().strip(),
            "quantite_analysee": r["qty_analysee_edit"].text().strip(),
            "num_lot":           r["num_lot_edit"].text().strip(),
            "num_acte":          r["num_acte_edit"].text().strip(),
            "num_cert":          r["num_cert_edit"].text().strip(),
            "classe":            r["classe_edit"].text().strip(),
            "date_production":   r["date_prod_edit"].date().toString("dd/MM/yyyy"),
            "date_peremption":   r["date_peremp_edit"].date().toString("dd/MM/yyyy"),
            "num_prelevement":   r["num_prelev_edit"].text().strip(),
            "date_pv":           r["date_pv_edit"].date().toString("dd/MM/yyyy"),
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
            ("N° Prélèvement", r["num_prelev_edit"].text().strip(), r["num_prelev_edit"]),
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

    def _on_row_print_clicked(self, row_index: int):
        r = self._rows[row_index]
        if r["cc_cb"].isChecked():
            cert_type = "CC"
        elif r["cnc_cb"].isChecked():
            cert_type = "CNC"
        else:
            QMessageBox.warning(
                self,
                "Type manquant",
                f"Veuillez sélectionner CC ou CNC pour « {r['name']} ».",
            )
            return

        if not self._validate_required_fields(row_index):
            return

        extras = self._row_extras(row_index)
        printer = CertificatePrinter(self)
        printer.print_certificates(self.form, [(r["pid"], r["name"], cert_type, extras)])

        # Marquer la ligne comme imprimée (bordure verte)
        self._printed_pids.add(r["pid"])
        self._apply_row_green(row_index)

    # ------------------------------------------------------------------
    # Coloriage vert des lignes déjà imprimées
    # ------------------------------------------------------------------

    def _apply_row_green(self, row_index: int):
        """Colore en vert le fond de toute la ligne (items + widgets)."""
        item = self._table.item(row_index, _COL_DESIGNATION)
        if item:
            item.setBackground(QColor(_GREEN))
        for col in range(1, _COL_COUNT):
            widget = self._table.cellWidget(row_index, col)
            if widget:
                _set_widget_bg(widget, _GREEN)


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


def _set_widget_bg(widget: QWidget, color_hex: str):
    """Applique récursivement la couleur de fond sur un widget et ses enfants QWidget."""
    widget.setStyleSheet(f"background-color: {color_hex};")
    for child in widget.findChildren(QWidget):
        child.setStyleSheet(f"background-color: {color_hex};")
