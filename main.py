"""This is the main entry point of the application."""
import sys
import tempfile
import traceback
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QMessageBox

from models.database.db_config import database_config_requires_setup, get_database_settings
from models.database_manager import DatabaseManager
from services.auth_service import AuthService
from views.auth import DatabaseConfigDialog
from views.auth import LoginDialog, SetupAdminDialog
from views.foundation.window import Window
from views.foundation.main_layout import MainLayout
from views.foundation.globals import GlobalVariable
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
            if exec_startup_dialog(dialog) != QtWidgets.QDialog.Accepted or not dialog.created_user:
                return None
            return dialog.created_user

        dialog = LoginDialog(auth_service, parent)
        if exec_startup_dialog(dialog) != QtWidgets.QDialog.Accepted or not dialog.authenticated_user:
            return None
        return dialog.authenticated_user
    finally:
        auth_service.close()


def exec_startup_dialog(dialog: QtWidgets.QDialog) -> int:
    dialog.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog.exec()


class StartupSplash:
    def __init__(self, app):
        self.app = app
        self._closed = False
        image_path = resolve_resource_path("images/image.png")
        pixmap = QtGui.QPixmap(str(image_path)) if image_path.exists() else QtGui.QPixmap()
        if pixmap.isNull():
            self.splash = None
            return

        self.splash = QtWidgets.QSplashScreen(
            pixmap,
            QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.FramelessWindowHint,
        )
        self.splash.setMask(pixmap.mask())

    def show(self, message=""):
        if self.splash is None:
            return
        self._closed = False
        self.splash.show()
        self.show_message(message)
        QtCore.QTimer.singleShot(2000, self.close)

    def show_message(self, message=""):
        if self.splash is None:
            return
        self.splash.showMessage(
            message,
            QtCore.Qt.AlignmentFlag.AlignBottom | QtCore.Qt.AlignmentFlag.AlignHCenter,
            QtGui.QColor("white"),
        )
        self.app.processEvents()

    def finish(self, window):
        if self.splash is None or self._closed:
            return
        self.splash.finish(window)
        self._closed = True

    def close(self):
        if self.splash is None or self._closed:
            return
        self.splash.close()
        self._closed = True


class ApplicationController:
    def __init__(self, app):
        self.app = app
        self.window = Window()
        self.main_layout = None
        self.splash = StartupSplash(app)

    def start(self) -> int:
        self.splash.show("Chargement de l'application...")
        try:
            self.splash.show_message("Chargement de la configuration...")
            if not self._ensure_database_configuration():
                self.splash.close()
                return 0

            self.splash.show_message("Initialisation de la base de données...")
            self._initialize_database()

            self.splash.show_message("Authentification...")
            if not self._authenticate_and_show_main_view():
                self.splash.close()
                return 0

            self.window.show()
            self.splash.finish(self.window)
            return self.app.exec()
        except Exception:
            self.splash.close()
            raise

    def handle_logout(self):
        GlobalVariable.clear_current_user()
        if not self._authenticate_and_show_main_view():
            self.window.close()
            self.app.quit()

    def _authenticate_and_show_main_view(self) -> bool:
        user = authenticate_startup_user()
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

    def _ensure_database_configuration(self) -> bool:
        if not database_config_requires_setup():
            return True

        dialog = DatabaseConfigDialog(first_run=True)
        return exec_startup_dialog(dialog) == QtWidgets.QDialog.Accepted

    def _initialize_database(self):
        try:
            DatabaseManager.create_tables()
        except Exception as exc:
            settings = get_database_settings()
            if settings['engine'] == 'mysql':
                host = settings['mysql']['host']
                port = settings['mysql']['port']
                database_name = settings['mysql']['database']
                raise RuntimeError(
                    "Le demarrage a echoue pendant la connexion MySQL vers "
                    f"{host}:{port} (base {database_name}). Verifiez que le serveur est accessible, "
                    "puis relancez l'application."
                ) from exc
            raise


def log_startup_error(exc: Exception) -> Path:
    log_path = Path(tempfile.gettempdir()) / "fac-startup.log"
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
        "FaC - Erreur de demarrage",
        "L'application n'a pas pu démarrer.\n\n"
        f"Erreur: {exc}\n\n"
        f"Détails enregistrés dans: {log_path}"
    )

    if owns_app:
        app.quit()


if __name__ == "__main__":
    try:
        app = QtWidgets.QApplication([])
        apply_dark_theme(app)
        load_styles(app)
        controller = ApplicationController(app)
        sys.exit(controller.start())
    except Exception as exc:
        show_startup_error(exc)
        sys.exit(1)