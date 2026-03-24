from PySide6 import QtWidgets,QtCore
from PySide6.QtCore import QDate
from views.foundation.templates.records import ListRecordTemplate
from models.standard_invoice import StandardInvoice

class StandardInvoiceRecord(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.standardinvoice = StandardInvoice()
        self.setObjectName("card")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        self.list_record = ListRecordTemplate(self.standardinvoice.headers, self.standardinvoice.data)
        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.list_record)
        self.load_records()

    def load_records(self):
        self.standardinvoice.data = self.standardinvoice.get_standard_invoices()
        self.list_record.update_data(self.standardinvoice.data)

    def load_invoice_data(self, invoice_id):
        invoice = self.standardinvoice.get_standard_invoice_by_id(invoice_id)
        if invoice:
            # Remplir le formulaire
            form = self.parent().form
            form.company_name_input.setText(invoice['company_name'] or '')
            form.stat_input.setText(invoice['stat'] or '')
            form.nif_input.setText(invoice['nif'] or '')
            form.address_input.setText(invoice['address'] or '')
            form.responsable_input.setText(invoice['resp'] or '')
            if hasattr(form, 'date_issue_input') and invoice['date_issue']:
                form.date_issue_input.setDate(QDate.fromString(str(invoice['date_issue']), "yyyy-MM-dd"))
            if hasattr(form, 'date_result_input') and invoice['date_result']:
                form.date_result_input.setDate(QDate.fromString(str(invoice['date_result']), "yyyy-MM-dd"))
            if hasattr(form, 'product_ref_input'):
                form.product_ref_input.setText(invoice['product_ref'] or '')
            
            # Afficher le numéro de facture
            if hasattr(form, 'standard_invoice_number'):
                form.standard_invoice_number.setText(f"N° facture: {invoice['id']}")
            
            # Enregistrer l'ID sélectionné pour une modification sur Enregistrer
            if hasattr(self.parent().parent(), 'body_layout'):
                self.parent().parent().body_layout.current_invoice_id = invoice_id

            # Important: reset any previous invoice selection before applying this one
            self.parent().parent().body_layout.product_manager.clear_selection()

            # Sélectionner les produits avec leurs Ref.b.analyse sauvegardés
            selected_items = self.standardinvoice.get_invoice_items_with_refs(invoice_id, 'standard')
            selected_products = [row['product_id'] for row in selected_items]
            ref_mapping = {
                row['product_id']: row.get('ref_b_analyse')
                for row in selected_items
                if row.get('ref_b_analyse') is not None
            }
            num_act_mapping = {
                row['product_id']: row.get('num_act')
                for row in selected_items
                if row.get('num_act') is not None and str(row.get('num_act')).strip() != ''
            }
            self.parent().parent().body_layout.product_manager.select_products(selected_products, ref_mapping=ref_mapping, num_act_mapping=num_act_mapping)
            self.parent().parent().body_layout.product_manager.set_loaded_record_locked(True)
            
            # Mettre à jour le total
            self.parent().parent().body_layout.update_total_display()

    def delete_invoice(self, invoice_id):
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, 'Confirmation', f"Êtes-vous sûr de vouloir supprimer la facture {invoice_id} ?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.standardinvoice.delete_standard_invoice(invoice_id)
            self.load_records()

        