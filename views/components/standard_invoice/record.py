from PySide6 import QtWidgets,QtCore
from views.foundation.templates.records import ListRecordTemplate
from models.standard_invoice import StandardInvoice

class StandardInvoiceRecord(QtWidgets.QWidget):
    standardinvoice = StandardInvoice()
    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        List_record = ListRecordTemplate(self.standardinvoice.headers, self.standardinvoice.data)
        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(List_record)

        