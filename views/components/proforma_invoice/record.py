from views.foundation.templates.records import ListRecordTemplate
from models.proforma_invoice import ProformaInvoice
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import QDate
class ProformaInvoiceRecord(QtWidgets.QWidget):
    proformainvoice=ProformaInvoice()
    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.list_record = ListRecordTemplate(self.proformainvoice.headers,self.proformainvoice.data)
        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.list_record)
        self.load_records()

    def load_records(self):
        self.proformainvoice.data = self.proformainvoice.get_proforma_invoices()
        self.list_record.update_data(self.proformainvoice.data)

    def load_invoice_data(self, invoice_id):
        invoice = self.proformainvoice.get_proforma_invoice_by_id(invoice_id)
        if invoice:
            # Remplir le formulaire
            form = self.parent().form
            form.company_name_input.setText(invoice['company_name'] or '')
            form.nif_input.setText(invoice['nif'] or '')
            form.stat_input.setText(invoice['stat'] or '')
            form.responsable_input.setText(invoice['resp'] or '')
            if hasattr(form, 'date_input') and invoice['date']:
                form.date_input.setDate(QDate.fromString(str(invoice['date']), "yyyy-MM-dd"))
            
            # Enregistrer l'ID sélectionné pour une modification sur Enregistrer
            if hasattr(self.parent().parent(), 'body_layout'):
                self.parent().parent().body_layout.current_invoice_id = invoice_id

            # Sélectionner les produits
            selected_products = self.proformainvoice.get_invoice_items(invoice_id, 'proforma')
            self.parent().parent().body_layout.product_manager.select_products(selected_products)
            
            # Mettre à jour le total
            self.parent().parent().body_layout.update_total_display()