from PySide6 import QtWidgets
from views.foundation.head_layout import HeadLayout
from views.foundation.body_layout import BodyLayout
class MainLayout(QtWidgets.QWidget):
    def __init__(self,parent):
        super().__init__(parent)
        self.layout = QtWidgets.QVBoxLayout(self)
        self.head_layout = HeadLayout(self)
        self.body_layout = BodyLayout(self)
        self.layout.addWidget(self.head_layout,stretch=1)
        self.layout.addWidget(self.body_layout,stretch=1)

    # def clear_layout(self, layout):
    #     while layout.count():
    #         child = layout.takeAt(0)
    #         if child.widget():
    #             child.widget().deleteLater()
                    
    # def show_standard_invoice_form(self):
    #     self.clear_layout(self)
    #     form = StandardInvoiceForm()
    #     self.addWidget(form.company_name_label)
    #     self.addWidget(form.invoice_number_label)

