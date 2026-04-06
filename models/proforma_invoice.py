from models.database_manager import DatabaseManager

class ProformaInvoice(DatabaseManager):
    table_name = "proform_invoice"
    headers = ["N° fact", "Raison sociale","Date","Responsable", "Total"]
    data = []

    def get_proforma_invoices(self):
        return DatabaseManager.get_proforma_invoices(self)
    
    def get_invoice_items(self, invoice_id, invoice_type):
        return DatabaseManager.get_invoice_items(self, invoice_id, invoice_type)
    
    def get_proforma_invoice_by_id(self, invoice_id):
        return DatabaseManager.get_proforma_invoice_by_id(self, invoice_id)