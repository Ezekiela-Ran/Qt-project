class ConvertToStandardAction:
    @staticmethod
    def execute(body_layout):
        main_layout = body_layout.parent()
        if not hasattr(main_layout, "head_layout") or not hasattr(main_layout.head_layout, "form"):
            return

        proforma_form = main_layout.head_layout.form
        selected_line_items = body_layout.product_manager.get_preview_line_items()

        main_layout.menubar_click_standard()

        standard_form = main_layout.head_layout.form
        standard_form.company_name_input.setText(proforma_form.company_name_input.text())
        standard_form.responsable_input.setText(proforma_form.responsable_input.text())
        standard_form.stat_input.setText(proforma_form.stat_input.text())
        standard_form.nif_input.setText(proforma_form.nif_input.text())
        standard_form.address_input.setText(proforma_form.address_input.text())

        main_layout.body_layout.product_manager.select_products([], line_items=selected_line_items)
        main_layout.body_layout.update_total_display()
