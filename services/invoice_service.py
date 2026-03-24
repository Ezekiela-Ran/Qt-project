from models.database_manager import DatabaseManager

class InvoiceService:
    def __init__(self):
        self.db = DatabaseManager()

    def save_standard_invoice(self, company_name, stat, nif, address, date_issue, date_result, product_ref, responsable, total, selected_products, selected_refs=None, selected_num_acts=None):
        return self.db.save_standard_invoice(company_name, stat, nif, address, date_issue, date_result, product_ref, responsable, total, selected_products, selected_refs, selected_num_acts)

    def update_standard_invoice(self, invoice_id, company_name, stat, nif, address, date_issue, date_result, product_ref, responsable, total, selected_products, selected_refs=None, selected_num_acts=None):
        return self.db.update_standard_invoice(invoice_id, company_name, stat, nif, address, date_issue, date_result, product_ref, responsable, total, selected_products, selected_refs, selected_num_acts)

    def save_proforma_invoice(self, company_name, nif, stat, date, responsable, total, selected_products):
        return self.db.save_proforma_invoice(company_name, nif, stat, date, responsable, total, selected_products)

    def update_proforma_invoice(self, invoice_id, company_name, nif, stat, date, responsable, total, selected_products):
        return self.db.update_proforma_invoice(invoice_id, company_name, nif, stat, date, responsable, total, selected_products)

    def get_standard_invoices(self):
        return self.db.get_standard_invoices()

    def get_proforma_invoices(self):
        return self.db.get_proforma_invoices()

    def delete_standard_invoice(self, invoice_id):
        return self.db.delete_standard_invoice(invoice_id)

    def delete_proforma_invoice(self, invoice_id):
        return self.db.delete_proforma_invoice(invoice_id)