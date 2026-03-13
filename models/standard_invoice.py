# from models.invoices_model import InvoicesModel
from PySide6 import QtWidgets

class StandardInvoice:
    table_name = "standard_invoice"
    headers = ["Raison sociale","Adresse","Date d'émission","Date de resultat","réference produit","Responsable"]
    data = []