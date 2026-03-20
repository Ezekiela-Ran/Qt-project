from models.database_management import DatabaseManagement

class StandardInvoice(DatabaseManagement):
    table_name = "standard_invoice"
    headers = ["Raison sociale","Adresse","Date d'émission","Date de resultat","réference produit","Responsable"]
    data = []