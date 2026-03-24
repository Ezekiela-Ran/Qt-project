from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QVBoxLayout, QLineEdit, QLabel, QWidget, QHBoxLayout
from PySide6 import QtCore

class ListRecordTemplate(QWidget):

    def __init__(self, headers : list[str], data: list = None, parent=None):
        super().__init__(parent)
        self.headers = headers
        self.data = data or []
        self.all_data = self.data.copy()  # Keep original data for filtering
        
        layout = QVBoxLayout(self)
        
        # Search box
        search_layout = QHBoxLayout()
        self.search_label = QLabel("Rechercher:")
        self.search_input = QLineEdit()
        self.search_input.textChanged.connect(self.filter_data)
        search_layout.addWidget(self.search_label)
        search_layout.addWidget(self.search_input, 1)  # Take remaining space
        layout.addLayout(search_layout)
        
        # Table
        self.table = QTableWidget()
        self._setup_table()
        self._add_row()
        self.table.itemSelectionChanged.connect(self.on_item_selected)
        layout.addWidget(self.table)

    def _setup_table(self):
        # Nombre de colonnes dynamique
        self.table.setColumnCount(len(self.headers))
        self.table.setHorizontalHeaderLabels(self.headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)  # Enable sorting
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)

    def _add_row(self):
        self.table.setRowCount(0)
        data_to_show = self.data
        if not data_to_show:
            self.table.setRowCount(1)
            empty_text = "Aucun resultat pour cette recherche" if self.search_input.text().strip() else "Aucune donnee disponible dans la table"
            item = QTableWidgetItem(empty_text)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.table.setItem(0, 0, item)
            self.table.setSpan(0, 0, 1, len(self.headers))
            return
        self.table.setSortingEnabled(False)
        for row_data in data_to_show:
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)
            for column, value in enumerate(row_data):
                self.table.setItem(row_position, column, QTableWidgetItem(str(value)))
        self.table.setSortingEnabled(True)

    def on_item_selected(self):
        current_row = self.table.currentRow()
        if current_row >= 0 and hasattr(self.parent(), 'load_invoice_data'):
            invoice_id = self.table.item(current_row, 0).text()
            self.parent().load_invoice_data(invoice_id)

    def filter_data(self, _text=None):
        search_text = self.search_input.text().strip().lower()
        if not search_text:
            self.data = self.all_data.copy()
        else:
            self.data = [row for row in self.all_data if any(search_text in str(cell).lower() for cell in row)]
        self._add_row()

    def update_data(self, new_data):
        self.all_data = new_data.copy()
        self.data = self.all_data.copy()
        self.search_input.clear()
        self._add_row()