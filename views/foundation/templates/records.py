from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
from PySide6 import QtCore

class ListRecordTemplate(QTableWidget):

    def __init__(self, headers : list[str], data: list = None, parent=None):
        super().__init__(parent)
        self.headers = headers
        self.data = data or []
        self._setup_table()
        self._add_row()


    def _setup_table(self):
        # Nombre de colonnes dynamique
        self.setColumnCount(len(self.headers))
        self.setHorizontalHeaderLabels(self.headers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)
        self.verticalHeader().setVisible(False)

    def _add_row(self):
        if not self.data:
            self.setRowCount(1)
            item = QTableWidgetItem("Aucun donné disponible dans toute la table")
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.setItem(0, 0, item)
            self.setSpan(0, 0, 1, len(self.headers))
            return
        for row_data in self.data:
            row_position = self.rowCount()
            self.insertRow(row_position)
            for column, value in enumerate(row_data):
                self.setItem(row_position, column, QTableWidgetItem(str(value)))