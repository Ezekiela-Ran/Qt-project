from PySide6 import QtWidgets

class MainLayout(QtWidgets.QVBoxLayout):
    def __init__(self):
        super().__init__()
        
        self.addWidget(QtWidgets.QLabel("Hello, World!"))
        self.addWidget(QtWidgets.QLabel("Bye!"))