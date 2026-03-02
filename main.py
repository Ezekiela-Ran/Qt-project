"""
    This is the main entry point of the application
"""
import sys
from PySide6 import QtWidgets
from views.components.menu_bar import MenuBar
from views.foundation.window import Window
from views.foundation.main_layout import MainLayout

def load_styles(app):
        with open("styles/style.qss", "r") as f:
            app.setStyleSheet(f.read())

if __name__ == "__main__":
    
    app = QtWidgets.QApplication([])


    win = Window()
    
    load_styles(app)
    
    menu_bar = MenuBar(win)
    win.window_layout.addWidget(menu_bar)

    
    main_layout = MainLayout(win)
    win.window_layout.addWidget(main_layout)

    # win.setLayout(main_layout.head)
    
    win.show()
    
    
    sys.exit(app.exec())