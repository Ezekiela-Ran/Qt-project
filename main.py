"""
    This is the main entry point of the application
"""
import sys
from PySide6 import QtWidgets
from views.components.menu_bar import MenuBar
from views.foundations.window import Window


        
if __name__ == "__main__":
    
    app = QtWidgets.QApplication([])

    win = Window()
    MenuBar(win)
    win.show()
    
    sys.exit(app.exec())