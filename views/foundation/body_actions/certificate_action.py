"""Action déclenchée par le bouton Certificat dans BodyLayout."""
from PySide6.QtWidgets import QMessageBox

from views.foundation.globals import GlobalVariable


class CertificateAction:
    @staticmethod
    def execute(body_layout):
        if GlobalVariable.invoice_type != "standard":
            QMessageBox.warning(
                body_layout,
                "Certificat",
                "Les certificats multi-factures sont disponibles uniquement pour les factures standard.",
            )
            return

        from views.certificate.work_queue_dialog import CertificateWorkQueueDialog

        dlg = CertificateWorkQueueDialog(body_layout, body_layout.db_manager)
        dlg.exec()
