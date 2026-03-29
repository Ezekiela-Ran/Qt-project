"""This is the main entry point of the application."""
import sys
import tempfile
import traceback
from pathlib import Path

from PySide6 import QtGui, QtWidgets
from PySide6.QtWidgets import QMessageBox

from services.auth_service import AuthService
from views.foundation.window import Window
from views.foundation.main_layout import MainLayout
from views.foundation.globals import GlobalVariable
from views.auth import LoginDialog, SetupAdminDialog
from models.database_manager import DatabaseManager
from utils.path_utils import resolve_resource_path


def load_styles(app):
    with open(resolve_resource_path("styles/style.qss"), "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())


def apply_dark_theme(app):
    app.setStyle("Fusion")

    dark_palette = QtGui.QPalette()
    dark_palette.setColor(QtGui.QPalette.ColorRole.Window, QtGui.QColor(30, 30, 30))
    dark_palette.setColor(QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(240, 240, 240))
    dark_palette.setColor(QtGui.QPalette.ColorRole.Base, QtGui.QColor(22, 22, 22))
    dark_palette.setColor(QtGui.QPalette.ColorRole.AlternateBase, QtGui.QColor(36, 36, 36))
    dark_palette.setColor(QtGui.QPalette.ColorRole.ToolTipBase, QtGui.QColor(30, 30, 30))
    dark_palette.setColor(QtGui.QPalette.ColorRole.ToolTipText, QtGui.QColor(240, 240, 240))
    dark_palette.setColor(QtGui.QPalette.ColorRole.Text, QtGui.QColor(240, 240, 240))
    dark_palette.setColor(QtGui.QPalette.ColorRole.Button, QtGui.QColor(45, 45, 45))
    dark_palette.setColor(QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(240, 240, 240))
    dark_palette.setColor(QtGui.QPalette.ColorRole.BrightText, QtGui.QColor(255, 99, 71))
    dark_palette.setColor(QtGui.QPalette.ColorRole.Link, QtGui.QColor(82, 168, 236))
    dark_palette.setColor(QtGui.QPalette.ColorRole.Highlight, QtGui.QColor(42, 130, 218))
    dark_palette.setColor(QtGui.QPalette.ColorRole.HighlightedText, QtGui.QColor(255, 255, 255))
    dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.Text, QtGui.QColor(120, 120, 120))
    dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText, QtGui.QColor(120, 120, 120))
    dark_palette.setColor(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.WindowText, QtGui.QColor(120, 120, 120))

    app.setPalette(dark_palette)


def authenticate_startup_user(parent=None):
    auth_service = AuthService()
    try:
        if not auth_service.has_admin():
            dialog = SetupAdminDialog(auth_service, parent)
            if dialog.exec() != QtWidgets.QDialog.Accepted or not dialog.created_user:
                return None
            return dialog.created_user

        dialog = LoginDialog(auth_service, parent)
        if dialog.exec() != QtWidgets.QDialog.Accepted or not dialog.authenticated_user:
            return None
        return dialog.authenticated_user
    finally:
        auth_service.close()


class ApplicationController:
    def __init__(self, app):
        self.app = app
        self.window = Window()
        self.main_layout = None

    def start(self) -> int:
        if not self._authenticate_and_show_main_view():
            return 0
        self.window.show()
        return self.app.exec()

    def handle_logout(self):
        GlobalVariable.clear_current_user()
        if not self._authenticate_and_show_main_view():
            self.window.close()
            self.app.quit()

    def _authenticate_and_show_main_view(self) -> bool:
        user = authenticate_startup_user(self.window)
        if not user:
            return False

        GlobalVariable.set_current_user(user)
        self._mount_main_layout()
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()
        return True

    def _mount_main_layout(self):
        while self.window.window_layout.count():
            item = self.window.window_layout.takeAt(0)
            widget = item.widget()
            if widget is None:
                continue
            cleanup = getattr(widget, "cleanup", None)
            if callable(cleanup):
                cleanup()
            widget.deleteLater()

        self.main_layout = MainLayout(self.window, on_logout=self.handle_logout)
        self.window.window_layout.addWidget(self.main_layout)


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
        apply_dark_theme(app)
        load_styles(app)
        controller = ApplicationController(app)
        sys.exit(controller.start())
    except Exception as exc:
        show_startup_error(exc)
        sys.exit(1)