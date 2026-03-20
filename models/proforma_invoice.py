from models.database_management import DatabaseManagement

class ProformaInvoice(DatabaseManagement):
    table_name = "proform_invoice"
    headers = ["N° de la facture proforma", "Raison sociale","Date","Responsable"]
    data = []