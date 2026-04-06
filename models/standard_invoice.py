from models.database_manager import DatabaseManager

class StandardInvoice(DatabaseManager):
    table_name = "standard_invoice"
    headers = ["N° fact", "Raison sociale", "Adresse", "Date d'émission", "Date de résultat", "Référence produit", "Responsable", "Total"]
    data = []

    def get_standard_invoices(self):
        return DatabaseManager.get_standard_invoices(self)
    
    def get_invoice_items(self, invoice_id, invoice_type):
        return DatabaseManager.get_invoice_items(self, invoice_id, invoice_type)

    def get_invoice_items_with_refs(self, invoice_id, invoice_type):
        return DatabaseManager.get_invoice_items_with_refs(self, invoice_id, invoice_type)
    
    def get_standard_invoice_by_id(self, invoice_id):
        return DatabaseManager.get_standard_invoice_by_id(self, invoice_id)