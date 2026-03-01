from PySide6 import QtWidgets
from views.components.invoices.form.standard import StandardInvoiceForm

class MainLayout(QtWidgets.QVBoxLayout):
    def __init__(self):
        super().__init__()
        
    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                    
    def show_standard_invoice_form(self):
        self.clear_layout(self)
        form = StandardInvoiceForm()
        self.addWidget(form.company_name_label)
        self.addWidget(form.invoice_number_label)