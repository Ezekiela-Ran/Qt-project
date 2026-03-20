from PySide6.QtWidgets import QWidget, QVBoxLayout
from views.foundation.head_layout import HeadLayout
from views.foundation.body_layout import BodyLayout
from views.components.menu_bar import MenuBar
from views.foundation.globals import GlobalVariable

class MainLayout(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.build_ui("standard")  # interface par défaut

    def build_ui(self, invoice_type: str):
        """Construit l'UI selon le type d'invoice ('standard' ou 'proforma')."""
        self.clear_layout()

        # Menu bar
        menu_bar = MenuBar(self)
        self.layout.addWidget(menu_bar)

        # Head layout
        self.head_layout = HeadLayout(self)
        self.head_layout.setMaximumHeight(200)

        # Body layout
        self.body_layout = BodyLayout(self)

        if invoice_type == "standard":
            self.head_layout.standard_invoice()
            GlobalVariable.invoice_type = "standard"
        elif invoice_type == "proforma":
            self.head_layout.proforma_invoice()
            GlobalVariable.invoice_type = "proforma"


        # Ajout au layout principal
        for widget, stretch in [(self.head_layout, 1), (self.body_layout, 1)]:
            self.layout.addWidget(widget, stretch)

    def menubar_click_standard(self):
        self.build_ui("standard")

    def menubar_click_proforma(self):
        self.build_ui("proforma")

    def clear_layout(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_sub_layout(child.layout())

    def clear_sub_layout(self, sub_layout):
        while sub_layout.count():
            child = sub_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_sub_layout(child.layout())
