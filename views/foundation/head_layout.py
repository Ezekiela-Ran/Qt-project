from PySide6 import QtWidgets
from PySide6.QtCore import Qt
from views.forms.form_factory import FormFactory
from views.forms.record_factory import RecordFactory
from views.foundation.globals import GlobalVariable


class HeadLayout(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("headLayout")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.head_layout = QtWidgets.QHBoxLayout(self)
        self.head_layout.setContentsMargins(10, 10, 10, 6)
        self.head_layout.setSpacing(10)

    def _apply_current_user_to_form(self):
        if hasattr(self, "form") and hasattr(self.form, "set_responsable_username"):
            self.form.set_responsable_username(GlobalVariable.current_username())

    def standard_invoice(self):
        self.form = FormFactory.create_standard_form()
        self.record = RecordFactory.create_standard_record()

        self.form.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.record.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self._apply_current_user_to_form()

        self.head_layout.addWidget(self.form, 1)
        self.head_layout.addWidget(self.record, 1)

    def proforma_invoice(self):
        self.form = FormFactory.create_proforma_form()
        self.record = RecordFactory.create_proforma_record()

        self.form.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self.record.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        self._apply_current_user_to_form()

        self.head_layout.addWidget(self.form, 1)
        self.head_layout.addWidget(self.record, 1)