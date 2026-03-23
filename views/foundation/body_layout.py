from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from views.components.standard_invoice.product_manager import ProductManager
from models.database_manager import DatabaseManager
from services.invoice_printer import InvoicePrinter
from services.invoice_service import InvoiceService
from services.product_service import ProductService
from utils.text_utils import TextUtils
from views.foundation.body_actions.calculate_total_action import CalculateTotalAction
from views.foundation.body_actions.clear_form_and_selection_action import ClearFormAndSelectionAction
from views.foundation.body_actions.convert_to_standard_action import ConvertToStandardAction
from views.foundation.body_actions.preview_invoice_action import PreviewInvoiceAction
from views.foundation.body_actions.print_invoice_action import PrintInvoiceAction
from views.foundation.body_actions.certificate_action import CertificateAction
from views.foundation.body_actions.save_invoice_action import SaveInvoiceAction
from views.foundation.body_actions.update_total_display_action import UpdateTotalDisplayAction

class BodyLayout(QtWidgets.QWidget):
    def __init__(self, parent=None, invoice_type="standard"):
        super().__init__(parent)

        # Layout principal
        self.body_layout = QtWidgets.QVBoxLayout(self)
        self.body_layout.setContentsMargins(0, 0, 0, 0)

        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Services
        self.invoice_printer = InvoicePrinter(self)
        self.invoice_service = InvoiceService()
        self.product_service = ProductService()
        self.db_manager = DatabaseManager()

        # Gestion des produits:
        self.product_manager = ProductManager(self.product_service, invoice_type)
        self.product_manager.setObjectName("productType")
        self.product_manager.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Label pour le total
        self.net_a_payer_label = QtWidgets.QLabel("Net à payer: 0 Ar (ZERO ARIARY)")
        self.net_a_payer_label.setObjectName("netAPayerLabel")
        self.net_a_payer_label.setAlignment(Qt.AlignCenter)

        # Bouton enregistrer
        self.save_button = QtWidgets.QPushButton("Enregistrer")
        self.save_button.setObjectName("saveButton")

        # Bouton imprimer
        self.print_button = QtWidgets.QPushButton("Imprimer")
        self.print_button.setObjectName("printButton")

        # Bouton aperçu
        self.preview_button = QtWidgets.QPushButton("Aperçu")
        self.preview_button.setObjectName("previewButton")

        # Bouton convertir (pour proforma)
        self.convert_button = QtWidgets.QPushButton("Convertir")
        self.convert_button.setObjectName("convertButton")

        # Bouton certificat CC/CNC
        self.certificate_button = QtWidgets.QPushButton("Certificat")
        self.certificate_button.setObjectName("certificateButton")

        # Layout pour le total et les boutons
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addWidget(self.net_a_payer_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.save_button)
        bottom_layout.addWidget(self.print_button)
        bottom_layout.addWidget(self.preview_button)
        if invoice_type != "proforma":
            bottom_layout.addWidget(self.certificate_button)
        if invoice_type == "proforma":
            bottom_layout.addWidget(self.convert_button)

        self.body_layout.addWidget(self.product_manager)
        self.body_layout.addLayout(bottom_layout)

        # ID de la facture en cours de modification (None = nouvelle facture)
        self.current_invoice_id = None

        # Connecter le signal de changement de sélection pour mettre à jour le total
        self.product_manager.selection_changed.connect(self.update_total_display)

        # Connecter le bouton
        self.save_button.clicked.connect(self.save_invoice)
        self.print_button.clicked.connect(self.print_invoice)
        self.preview_button.clicked.connect(self.preview_invoice)
        if invoice_type != "proforma":
            self.certificate_button.clicked.connect(self.open_certificate_dialog)
        if invoice_type == "proforma":
            self.convert_button.clicked.connect(self.convert_to_standard)

        # Chargement du style QSS
        self._apply_stylesheet("styles/product_type.qss")
        self._apply_stylesheet("styles/body_layout.qss")

    def convert_to_standard(self):
        ConvertToStandardAction.execute(self)

    def number_to_words(self, number):
        return TextUtils.number_to_words(number)

    def save_invoice(self):
        SaveInvoiceAction.execute(self)

    def calculate_total(self):
        return CalculateTotalAction.execute(self)

    def clear_form_and_selection(self):
        ClearFormAndSelectionAction.execute(self)

    def update_total_display(self):
        UpdateTotalDisplayAction.execute(self)

    def preview_invoice(self):
        PreviewInvoiceAction.execute(self)

    def print_invoice(self):
        PrintInvoiceAction.execute(self)

    def open_certificate_dialog(self):
        CertificateAction.execute(self)

    def _apply_stylesheet(self, stylesheet_path):
        try:
            with open(stylesheet_path, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
            self.setStyleSheet(self.styleSheet() + "\n" + stylesheet)
        except FileNotFoundError:
            print(f"Stylesheet {stylesheet_path} not found.")
