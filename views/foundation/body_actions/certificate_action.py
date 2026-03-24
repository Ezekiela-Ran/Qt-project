"""
Action déclenchée par le bouton Certificat dans BodyLayout.

Vérifie qu'au moins un produit est sélectionné, récupère le formulaire client,
puis ouvre le dialogue de sélection CC / CNC.
"""
from PySide6.QtWidgets import QMessageBox


class CertificateAction:
    @staticmethod
    def execute(body_layout):
        if not body_layout.current_invoice_id:
            QMessageBox.warning(
                body_layout,
                "Certificat",
                "Veuillez selectionner un enregistrement",
            )
            return

        main_layout = body_layout.parent()
        if not hasattr(main_layout, "head_layout") or not hasattr(main_layout.head_layout, "form"):
            QMessageBox.warning(
                body_layout,
                "Certificat",
                "Impossible d'accéder au formulaire client.",
            )
            return

        selected_products = [
            pid
            for pid, selected in body_layout.product_manager.selected_products.items()
            if selected
        ]
        if not selected_products:
            QMessageBox.warning(
                body_layout,
                "Certificat",
                "Aucun produit sélectionné. Veuillez sélectionner au moins un produit.",
            )
            return

        form = main_layout.head_layout.form

        # Import différé pour éviter les dépendances circulaires
        from views.certificate.certificate_dialog import CertificateDialog

        dlg = CertificateDialog(
            body_layout,
            form,
            selected_products,
            body_layout.db_manager,
            product_manager=body_layout.product_manager,
        )
        dlg.exec()
