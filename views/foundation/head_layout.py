from PySide6 import QtWidgets
from views.components.invoices.form.standard import StandardInvoiceForm
from views.components.invoices.records.standard import StandardInvoiceRecord
from views.foundation.templates.invoices.form import FormTemplate

class HeadLayout(QtWidgets.QWidget):
    def __init__(self,parent):
        super().__init__(parent)
        
        
        self.head_layout = QtWidgets.QHBoxLayout(self)
        self.head_layout.setContentsMargins(0, 0, 0, 0)
        
        self.form = StandardInvoiceForm()
        self.record = StandardInvoiceRecord()

        # Facteur d’étirement
        self.head_layout.addWidget(self.form,3)
        self.head_layout.addWidget(self.record,2)