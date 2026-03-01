from PySide6 import QtWidgets

class FormTemplate:
    def __init__(self):
        self.company_name_label = QtWidgets.QLabel("Company Name")
        self.invoice_number_label = QtWidgets.QLabel("Invoice Number")