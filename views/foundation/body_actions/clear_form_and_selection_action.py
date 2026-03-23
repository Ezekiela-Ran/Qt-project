from PySide6.QtCore import QDate


class ClearFormAndSelectionAction:
    @staticmethod
    def execute(body_layout):
        main_layout = body_layout.parent()
        if hasattr(main_layout, "head_layout") and hasattr(main_layout.head_layout, "form"):
            form = main_layout.head_layout.form
            form.company_name_input.clear()
            form.responsable_input.clear()
            form.stat_input.clear()
            form.nif_input.clear()
            form.address_input.clear()

            if hasattr(form, "date_issue_input"):
                form.date_issue_input.setDate(QDate.currentDate())
            if hasattr(form, "date_result_input"):
                form.date_result_input.setDate(QDate.currentDate())
            if hasattr(form, "product_ref_input"):
                form.product_ref_input.clear()
            if hasattr(form, "date_input"):
                form.date_input.setDate(QDate.currentDate())

        body_layout.product_manager.clear_selection()
        body_layout.current_invoice_id = None
        body_layout.net_a_payer_label.setText("Net à payer: 0 Ar (ZERO ARIARY)")
