from PySide6.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QInputDialog
import datetime
from views.foundation.head_layout import HeadLayout
from views.foundation.body_layout import BodyLayout
from views.components.menu_bar import MenuBar
from views.foundation.globals import GlobalVariable
from views.auth import DatabaseConfigDialog, UserManagementDialog
from models.database_manager import DatabaseManager

class MainLayout(QWidget):
    def __init__(self, parent, on_logout=None):
        super().__init__(parent)
        self.on_logout = on_logout
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
        db = DatabaseManager()
        try:
            if db.has_invoice_history():
                QMessageBox.warning(
                    self,
                    "Initialisation impossible",
                    "Des factures existent déjà dans la base. L'ID de facture et la Ref.b.analyse ne peuvent plus être modifiés.",
                )
                return

            default_invoice_start = int(db.get_setting("invoice_id_start", 1) or 1)
            default_ref_start = int(db.get_setting("ref_b_analyse_start", 1) or 1)

            invoice_start, ok = QInputDialog.getInt(
                self,
                "Initialiser l'ID de facture",
                "Valeur de départ pour l'ID de facture :",
                value=default_invoice_start,
                minValue=1,
            )
            if not ok:
                return

            ref_start, ok = QInputDialog.getInt(
                self,
                "Initialiser Ref.b.analyse",
                "Valeur de départ pour Ref.b.analyse :",
                value=default_ref_start,
                minValue=1,
            )
            if not ok:
                return

            db.initialize_document_counters(invoice_start, ref_start)
            QMessageBox.information(
                self,
                "Initialisation réussie",
                f"Les prochains identifiants commenceront à {invoice_start} pour les factures et à {ref_start} pour Ref.b.analyse.",
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Initialisation impossible", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Erreur", f"L'initialisation a échoué : {exc}")
        finally:
            db.close()

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
