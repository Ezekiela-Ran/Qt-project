from PySide6.QtWidgets import QMessageBox

from views.foundation.globals import GlobalVariable


class PreviewInvoiceAction:
    @staticmethod
    def execute(body_layout):
        main_layout = body_layout.parent()
        if not hasattr(main_layout, "head_layout") or not hasattr(main_layout.head_layout, "form"):
            QMessageBox.warning(
                body_layout,
                "Aperçu impossible",
                "Impossible de générer l’aperçu. Vérifiez les données.",
            )
            return

        form = main_layout.head_layout.form
        line_items = body_layout.product_manager.get_preview_line_items()
        if not line_items:
            QMessageBox.warning(body_layout, "Aperçu impossible", "Aucun produit sélectionné.")
            return

        html = body_layout.invoice_printer.generate_invoice_html(
            form,
            GlobalVariable.invoice_type,
            line_items,
            body_layout.db_manager,
            invoice_id=body_layout.current_invoice_id,
        )
        body_layout.invoice_printer.preview_invoice(html)
