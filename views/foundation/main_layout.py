from PySide6 import QtCore
from PySide6.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QInputDialog, QProgressDialog
import datetime
from views.foundation.head_layout import HeadLayout
from views.foundation.body_layout import BodyLayout
from views.components.menu_bar import MenuBar
from views.foundation.globals import GlobalVariable
from views.auth import DatabaseConfigDialog, UserManagementDialog
from models.database_manager import DatabaseManager


class CounterInitializationWorker(QtCore.QObject):
    succeeded = QtCore.Signal(int, int, int, int)
    failed = QtCore.Signal(str, str)
    finished = QtCore.Signal()

    def __init__(self, invoice_start: int, ref_start: int, cert_cc_start: int, cert_cnc_start: int):
        super().__init__()
        self.invoice_start = int(invoice_start)
        self.ref_start = int(ref_start)
        self.cert_cc_start = int(cert_cc_start)
        self.cert_cnc_start = int(cert_cnc_start)

    @QtCore.Slot()
    def run(self):
        db = None
        try:
            db = DatabaseManager()
            db.initialize_document_counters(
                self.invoice_start,
                self.ref_start,
                self.cert_cc_start,
                self.cert_cnc_start,
            )
        except ValueError as exc:
            self.failed.emit("warning", str(exc))
        except Exception as exc:
            self.failed.emit("critical", f"L'initialisation a échoué : {exc}")
        else:
            self.succeeded.emit(
                self.invoice_start,
                self.ref_start,
                self.cert_cc_start,
                self.cert_cnc_start,
            )
        finally:
            if db is not None:
                db.close()
            self.finished.emit()

class MainLayout(QWidget):
    def __init__(self, parent, on_logout=None):
        super().__init__(parent)
        self.on_logout = on_logout
        self._counter_init_thread = None
        self._counter_init_worker = None
        self._counter_init_progress = None
        self._last_invoice_start = 1
        self._last_ref_start = 1
        self._last_cert_cc_start = 1
        self._last_cert_cnc_start = 1
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(8)
        self.build_ui("standard")  # interface par défaut

    def build_ui(self, invoice_type: str):
        """Construit l'UI selon le type d'invoice ('standard' ou 'proforma')."""
        self.clear_layout()

        # Menu bar
        menu_bar = MenuBar(self)
        self.layout.addWidget(menu_bar)

        # Head layout
        self.head_layout = HeadLayout(self)

        # Body layout
        self.body_layout = BodyLayout(self, invoice_type)
        self.head_layout.setSizePolicy(self.head_layout.sizePolicy().horizontalPolicy(), self.head_layout.sizePolicy().Policy.Expanding)
        self.body_layout.setSizePolicy(self.body_layout.sizePolicy().horizontalPolicy(), self.body_layout.sizePolicy().Policy.Expanding)

        if invoice_type == "standard":
            GlobalVariable.invoice_type = invoice_type
            self.head_layout.standard_invoice()
        elif invoice_type == "proforma":
            GlobalVariable.invoice_type = invoice_type
            self.head_layout.proforma_invoice()


        # Ajout au layout principal
        for widget, stretch in [(self.head_layout, 0), (self.body_layout, 1)]:
            self.layout.addWidget(widget, stretch)

    def menubar_click_standard(self):
        self.build_ui("standard")

    def menubar_click_proforma(self):
        self.build_ui("proforma")

    def menubar_click_initialize_counters(self):
        try:
            invoice_start, ok = QInputDialog.getInt(
                self,
                "Initialiser l'ID de facture",
                "Valeur de départ pour l'ID de facture :",
                value=self._last_invoice_start,
                minValue=1,
            )
            if not ok:
                return

            ref_start, ok = QInputDialog.getInt(
                self,
                "Initialiser Ref.b.analyse",
                "Valeur de départ pour Ref.b.analyse :",
                value=self._last_ref_start,
                minValue=1,
            )
            if not ok:
                return

            cert_cc_start, ok = QInputDialog.getInt(
                self,
                "Initialiser N° cert CC",
                "Valeur de départ pour le N° certificat CC :",
                value=self._last_cert_cc_start,
                minValue=1,
            )
            if not ok:
                return

            cert_cnc_start, ok = QInputDialog.getInt(
                self,
                "Initialiser N° cert CNC",
                "Valeur de départ pour le N° certificat CNC :",
                value=self._last_cert_cnc_start,
                minValue=1,
            )
            if not ok:
                return

            self._start_counter_initialization(invoice_start, ref_start, cert_cc_start, cert_cnc_start)
        except ValueError as exc:
            QMessageBox.warning(self, "Initialisation impossible", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"L'initialisation a échoué : {exc}")

    def _start_counter_initialization(self, invoice_start: int, ref_start: int, cert_cc_start: int, cert_cnc_start: int):
        if self._counter_init_thread is not None:
            QMessageBox.information(
                self,
                "Initialisation en cours",
                "Une initialisation des compteurs est déjà en cours sur ce poste.",
            )
            return

        self._counter_init_progress = QProgressDialog(
            "Initialisation des compteurs en cours...",
            None,
            0,
            0,
            self,
        )
        self._counter_init_progress.setWindowTitle("Initialisation")
        self._counter_init_progress.setCancelButton(None)
        self._counter_init_progress.setMinimumDuration(0)
        self._counter_init_progress.setWindowModality(QtCore.Qt.WindowModality.ApplicationModal)
        self._counter_init_progress.show()

        self._counter_init_thread = QtCore.QThread(self)
        self._counter_init_worker = CounterInitializationWorker(
            invoice_start,
            ref_start,
            cert_cc_start,
            cert_cnc_start,
        )
        self._counter_init_worker.moveToThread(self._counter_init_thread)

        self._counter_init_thread.started.connect(self._counter_init_worker.run)
        self._counter_init_worker.succeeded.connect(self._handle_counter_init_success)
        self._counter_init_worker.failed.connect(self._handle_counter_init_failure)
        self._counter_init_worker.finished.connect(self._counter_init_thread.quit)
        self._counter_init_worker.finished.connect(self._counter_init_worker.deleteLater)
        self._counter_init_thread.finished.connect(self._cleanup_counter_initialization)
        self._counter_init_thread.finished.connect(self._counter_init_thread.deleteLater)

        self._counter_init_thread.start()

    def _handle_counter_init_success(self, invoice_start: int, ref_start: int, cert_cc_start: int, cert_cnc_start: int):
        self._last_invoice_start = int(invoice_start)
        self._last_ref_start = int(ref_start)
        self._last_cert_cc_start = int(cert_cc_start)
        self._last_cert_cnc_start = int(cert_cnc_start)
        QMessageBox.information(
            self,
            "Initialisation réussie",
            (
                f"Les prochains identifiants commenceront à {invoice_start} pour les factures, "
                f"à {ref_start} pour Ref.b.analyse, à {cert_cc_start} pour les certificats CC "
                f"et à {cert_cnc_start} pour les certificats CNC."
            ),
        )

    def _handle_counter_init_failure(self, severity: str, message: str):
        if severity == "warning":
            QMessageBox.warning(self, "Initialisation impossible", message)
            return
        QMessageBox.critical(self, "Erreur", message)

    def _cleanup_counter_initialization(self):
        if self._counter_init_progress is not None:
            self._counter_init_progress.close()
            self._counter_init_progress.deleteLater()
            self._counter_init_progress = None
        self._counter_init_worker = None
        self._counter_init_thread = None

    def menubar_click_reset(self):
        db = DatabaseManager()
        try:
            current_year = datetime.date.today().year
            if not db.can_archive_and_reset(current_year):
                QMessageBox.information(
                    self,
                    "Réinitialisation indisponible",
                    f"La réinitialisation a déjà été effectuée pour l'année {current_year}.",
                )
                return

            reply = QMessageBox.question(
                self,
                "Réinitialisation",
                "Confirmer la réinitialisation : les données actuelles seront archivées pour l'année courante et les compteurs seront remis à 1. Continuer ?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

            db.archive_and_reset(current_year)
            QMessageBox.information(self, "Réinitialisation", "Archivage et réinitialisation terminés avec succès.")
        except ValueError as exc:
            QMessageBox.information(self, "Réinitialisation indisponible", str(exc))
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"La réinitialisation a échoué : {e}")
        finally:
            db.close()

    def menubar_click_manage_users(self):
        if not GlobalVariable.is_admin():
            QMessageBox.warning(self, "Accès refusé", "Seul un administrateur peut gérer les utilisateurs.")
            return
        dialog = UserManagementDialog(self, current_user=GlobalVariable.current_user)
        dialog.exec()

    def menubar_click_database_config(self):
        if not GlobalVariable.is_admin():
            QMessageBox.warning(self, "Accès refusé", "Seul un administrateur peut modifier la configuration de la base de données.")
            return
        dialog = DatabaseConfigDialog(self)
        dialog.exec()

    def menubar_click_logout(self):
        if not callable(self.on_logout):
            return
        reply = QMessageBox.question(
            self,
            "Déconnexion",
            "Voulez-vous vraiment vous déconnecter ?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self.on_logout()

    def clear_layout(self):
        while self.layout.count():
            child = self.layout.takeAt(0)
            if child.widget():
                cleanup = getattr(child.widget(), "cleanup", None)
                if callable(cleanup):
                    cleanup()
                child.widget().deleteLater()
            elif child.layout():
                self.clear_sub_layout(child.layout())

    def clear_sub_layout(self, sub_layout):
        while sub_layout.count():
            child = sub_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_sub_layout(child.layout())
