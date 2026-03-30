from PySide6.QtWidgets import QMessageBox

from views.foundation.globals import GlobalVariable


class PrintInvoiceAction:
    @staticmethod
    def execute(body_layout):
        if not body_layout.current_invoice_id:
            QMessageBox.warning(
                body_layout,
                "Impression impossible",
                "Veuillez d'abord enregistrer la facture avant de l'imprimer.",
            )
            return

        main_layout = body_layout.parent()
        if not hasattr(main_layout, "head_layout") or not hasattr(main_layout.head_layout, "form"):
            QMessageBox.warning(
                body_layout,
                "Impression impossible",
                "Impossible de générer l’impression. Vérifiez les données.",
            )
            return

        form = main_layout.head_layout.form
        selected_products = [
            pid for pid, selected in body_layout.product_manager.selected_products.items() if selected
        ]
        if not selected_products:
            QMessageBox.warning(body_layout, "Impression impossible", "Aucun produit sélectionné.")
            return

        pm = body_layout.product_manager
        try:
            order = pm.selection_order
        except Exception:
            order = list(selected_products)
        selected_set = {pid for pid, sel in pm.selected_products.items() if sel}
        ordered_selected = [pid for pid in order if pid in selected_set]
        if not ordered_selected:
            ordered_selected = [pid for pid in selected_products]
        ref_mapping = pm.get_selected_ref_mapping()
        num_act_mapping = pm.get_selected_num_act_mapping()

        html = body_layout.invoice_printer.generate_invoice_html(
            form,
            GlobalVariable.invoice_type,
            ordered_selected,
            body_layout.db_manager,
            invoice_id=body_layout.current_invoice_id,
            ref_mapping=ref_mapping,
            num_act_mapping=num_act_mapping,
        )
        body_layout.invoice_printer.print_invoice(html)
