from views.foundation.templates.records import ListRecordTemplate
from models.proforma_invoice import ProformaInvoice
from PySide6 import QtCore, QtWidgets
class ProformaInvoiceRecord(QtWidgets.QWidget):
    proformainvoice=ProformaInvoice()
    def __init__(self):
        super().__init__()
        self.setObjectName("card")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)
        List_record = ListRecordTemplate(self.proformainvoice.headers,self.proformainvoice.data)
        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(List_record)