"""
    This is the main entry point of the application
"""
import sys
from PySide6 import QtWidgets
from views.components.menu_bar import MenuBar
from views.foundation.window import Window
from views.foundation.main_layout import MainLayout
    
if __name__ == "__main__":
    
    app = QtWidgets.QApplication([])

    win = Window()
    
    MenuBar(win)
    main_layout = MainLayout()
    win.setLayout(main_layout)
    
    win.show()
    
    
    sys.exit(app.exec())