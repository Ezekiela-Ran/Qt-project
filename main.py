"""This is the main entry point of the application."""
import sys
import tempfile
import traceback
from pathlib import Path

from PySide6 import QtWidgets
from PySide6.QtWidgets import QMessageBox

from views.foundation.window import Window
from views.foundation.main_layout import MainLayout
from models.database_manager import DatabaseManager
from utils.path_utils import resolve_resource_path


def load_styles(app):
    with open(resolve_resource_path("styles/style.qss"), "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())


def log_startup_error(exc: Exception) -> Path:
    log_path = Path(tempfile.gettempdir()) / "lfca-startup.log"
    details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    log_path.write_text(details, encoding="utf-8")
    return log_path


def show_startup_error(exc: Exception):
    log_path = log_startup_error(exc)
    app = QtWidgets.QApplication.instance()
    owns_app = False
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
        owns_app = True

    QMessageBox.critical(
        None,
        "LFCA - Startup error",
        "L'application n'a pas pu démarrer.\n\n"
        f"Erreur: {exc}\n\n"
        f"Détails enregistrés dans: {log_path}"
    )

    if owns_app:
        app.quit()


if __name__ == "__main__":
    try:
        DatabaseManager.create_tables()
        app = QtWidgets.QApplication([])

        win = Window()

        load_styles(app)

        main_layout = MainLayout(win)

        win.window_layout.addWidget(main_layout)

        win.show()

        sys.exit(app.exec())
    except Exception as exc:
        show_startup_error(exc)
        sys.exit(1)