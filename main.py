"""
    This is the main entry point of the application
"""
import sys
from PySide6 import QtWidgets
from views.foundation.window import Window
from views.foundation.main_layout import MainLayout
from models.database_management import DatabaseManagement


def load_styles(app):
        with open("styles/style.qss", "r") as f:
            app.setStyleSheet(f.read())


if __name__ == "__main__":
    
    DatabaseManagement.create_tables()

    app = QtWidgets.QApplication([])


    win = Window()
    
    load_styles(app)
    
    

    main_layout = MainLayout(win)
    
    win.window_layout.addWidget(main_layout)
    
    win.show()
    
    
    sys.exit(app.exec())