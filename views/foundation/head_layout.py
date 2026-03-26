from PySide6 import QtWidgets
from views.forms.form_factory import FormFactory
from views.forms.record_factory import RecordFactory


class HeadLayout(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.head_layout = QtWidgets.QHBoxLayout(self)
        self.head_layout.setContentsMargins(0, 0, 0, 0)
        self.head_layout.setSpacing(8)

    def standard_invoice(self):
        self.form = FormFactory.create_standard_form()
        self.record = RecordFactory.create_standard_record()

        self.form.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.record.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

        self.head_layout.addWidget(self.form, 1)
        self.head_layout.addWidget(self.record, 1)

    def proforma_invoice(self):
        self.form = FormFactory.create_proforma_form()
        self.record = RecordFactory.create_proforma_record()

        self.form.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.record.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)

        self.head_layout.addWidget(self.form, 1)
        self.head_layout.addWidget(self.record, 1)