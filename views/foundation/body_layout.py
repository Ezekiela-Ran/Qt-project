from PySide6 import QtWidgets,QtCore

class BodyLayout(QtWidgets.QWidget):
    def __init__(self,parent):
        super().__init__(parent)
        self.body_layout = QtWidgets.QVBoxLayout(self)
        self.setObjectName("card")
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)    
