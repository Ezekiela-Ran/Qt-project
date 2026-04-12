from views.foundation.templates.records import ListRecordTemplate
from models.proforma_invoice import ProformaInvoice
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QDate
from views.foundation.globals import GlobalVariable


AUTO_REFRESH_INTERVAL_MS = 5000

class ProformaInvoiceRecord(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.proformainvoice = ProformaInvoice()
        self.setObjectName("card")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.list_record = ListRecordTemplate(
            self.proformainvoice.headers,
            self.proformainvoice.data,
            searchable_columns=[0, 1],
        )
        self.list_record.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list_record)
        self.load_records()
        self.refresh_timer = QtCore.QTimer(self)
        self.refresh_timer.setInterval(AUTO_REFRESH_INTERVAL_MS)
        self.refresh_timer.timeout.connect(self.refresh_records_silently)
        self.refresh_timer.start()

    def load_records(self):
        self.proformainvoice.data = self.proformainvoice.get_proforma_invoices()
        self.list_record.update_data(self.proformainvoice.data)

    def refresh_records_silently(self):
        if not self.isVisible():
            return
        try:
            latest_data = self.proformainvoice.get_proforma_invoices()
        except Exception:
            return
        if latest_data == self.list_record.all_data:
            return
        self.proformainvoice.data = latest_data
        self.list_record.update_data(latest_data, preserve_state=True)

    def load_invoice_data(self, invoice_id):
        invoice = self.proformainvoice.get_proforma_invoice_by_id(invoice_id)
        if invoice:
            # Remplir le formulaire
            form = self.parent().form
            form.company_name_input.setText(invoice['company_name'] or '')
            form.nif_input.setText(invoice['nif'] or '')
            form.stat_input.setText(invoice['stat'] or '')
            form.responsable_input.setText(GlobalVariable.current_username())
            if hasattr(form, 'date_input') and invoice['date']:
                form.date_input.setDate(QDate.fromString(str(invoice['date']), "yyyy-MM-dd"))
            if hasattr(form, 'proforma_invoice_number'):
                form.proforma_invoice_number.setText(str(invoice['id']))
            
            # Enregistrer l'ID sélectionné pour une modification sur Enregistrer
            if hasattr(self.parent().parent(), 'body_layout'):
                self.parent().parent().body_layout.current_invoice_id = invoice_id

            # Important: reset any previous invoice selection before applying this one
            self.parent().parent().body_layout.product_manager.clear_selection()

            # Sélectionner les produits
            selected_items = self.proformainvoice.get_invoice_items_with_refs(invoice_id, 'proforma')
            self.parent().parent().body_layout.product_manager.select_products([], line_items=selected_items)
            self.parent().parent().body_layout.product_manager.set_loaded_record_locked(True)
            
            # Mettre à jour le total
            self.parent().parent().body_layout.update_total_display()

    def delete_invoice(self, invoice_id):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, 'Confirmation', f"Êtes-vous sûr de vouloir supprimer la facture proforma {invoice_id} ?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.proformainvoice.delete_proforma_invoice(invoice_id)
            self.load_records()

    def cleanup(self):
        if hasattr(self, 'refresh_timer'):
            self.refresh_timer.stop()
        close = getattr(self.proformainvoice, 'close', None)
        if callable(close):
            close()