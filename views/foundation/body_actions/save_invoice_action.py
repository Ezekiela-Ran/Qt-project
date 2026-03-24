from PySide6.QtWidgets import QMessageBox
from views.foundation.globals import GlobalVariable


class SaveInvoiceAction:
    @staticmethod
    def _allocate_refs_for_save(body_layout, selected_products):
        pm = body_layout.product_manager
        allocated_refs = dict(pm.get_selected_ref_mapping())
        ordered_selected = [
            pid for pid in pm.selection_order
            if pid in selected_products and pm.selected_products.get(pid, False)
        ]

        for pid in ordered_selected:
            if pid in allocated_refs:
                continue
            allocated_refs[pid] = int(body_layout.product_service.allocate_next_ref_b_analyse())

        return allocated_refs

    @staticmethod
    def _refresh_record_list(main_layout, body_layout):
        head_layout = getattr(main_layout, "head_layout", None)
        record_widget = getattr(head_layout, "record", None)
        if not record_widget:
            return

        if hasattr(record_widget, "load_records"):
            record_widget.load_records()
            return

        list_record = getattr(record_widget, "list_record", None)
        if not list_record or not hasattr(list_record, "update_data"):
            return

        if GlobalVariable.invoice_type == "standard":
            data = body_layout.invoice_service.get_standard_invoices()
        else:
            data = body_layout.invoice_service.get_proforma_invoices()
        list_record.update_data(data)

    @staticmethod
    def execute(body_layout):
        main_layout = body_layout.parent()
        if not hasattr(main_layout, "head_layout") or not hasattr(main_layout.head_layout, "form"):
            return

        form = main_layout.head_layout.form
        company_name = form.company_name_input.text().strip()
        responsable = form.responsable_input.text().strip()
        stat = form.stat_input.text()
        nif = form.nif_input.text()

        errors = []
        if not company_name:
            errors.append("Raison sociale est obligatoire")
        if not responsable:
            errors.append("Responsable est obligatoire")

        selected_products = [
            pid for pid, selected in body_layout.product_manager.selected_products.items() if selected
        ]
        if not selected_products:
            errors.append("Au moins un produit doit être sélectionné")

        pm = body_layout.product_manager
        selected_refs = pm.get_selected_ref_mapping() if GlobalVariable.invoice_type == "standard" else {}
        selected_num_acts = pm.get_selected_num_act_mapping() if GlobalVariable.invoice_type == "standard" else {}
        if GlobalVariable.invoice_type == "standard":
            if not body_layout.current_invoice_id:
                selected_refs = SaveInvoiceAction._allocate_refs_for_save(body_layout, selected_products)
                pm.selected_refs.update(selected_refs)

            for pid in selected_products:
                if pid not in selected_refs:
                    product = body_layout.product_service.get_product_by_id(pid)
                    product_name = product["product_name"] if product else "inconnu"
                    errors.append(
                        f"Ref.b.analyse manquant pour le produit {product_name}. Désélectionnez puis resélectionnez le produit."
                    )

            seen_num_act = {}
            for pid in selected_products:
                num_act = selected_num_acts.get(pid)
                if num_act is None:
                    continue
                if num_act in seen_num_act:
                    first_pid = seen_num_act[num_act]
                    first_product = body_layout.product_service.get_product_by_id(first_pid)
                    second_product = body_layout.product_service.get_product_by_id(pid)
                    first_name = first_product["product_name"] if first_product else str(first_pid)
                    second_name = second_product["product_name"] if second_product else str(pid)
                    errors.append(
                        f"N°Acte dupliqué dans la facture: '{num_act}' est utilisé pour {first_name} et {second_name}."
                    )
                else:
                    seen_num_act[num_act] = pid

        if errors:
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Critical)
            msg.setWindowTitle("Erreur de validation")
            msg.setText("L'enregistrement ne peut pas être effectué pour les raisons suivantes:")
            msg.setDetailedText("\n".join(errors))
            msg.exec()
            return

        if GlobalVariable.invoice_type == "standard":
            date_issue = form.date_issue_input.date().toString("yyyy-MM-dd") if hasattr(form, "date_issue_input") else ""
            date_result = form.date_result_input.date().toString("yyyy-MM-dd") if hasattr(form, "date_result_input") else ""
            product_ref = form.product_ref_input.text() if hasattr(form, "product_ref_input") else ""
            address = form.address_input.text()
            total = body_layout.calculate_total()

            if body_layout.current_invoice_id:
                invoice_id = body_layout.invoice_service.update_standard_invoice(
                    body_layout.current_invoice_id,
                    company_name,
                    stat,
                    nif,
                    address,
                    date_issue,
                    date_result,
                    product_ref,
                    responsable,
                    total,
                    selected_products,
                    selected_refs,
                    selected_num_acts,
                )
            else:
                invoice_id = body_layout.invoice_service.save_standard_invoice(
                    company_name,
                    stat,
                    nif,
                    address,
                    date_issue,
                    date_result,
                    product_ref,
                    responsable,
                    total,
                    selected_products,
                    selected_refs,
                    selected_num_acts,
                )

            if hasattr(form, "standard_invoice_number"):
                form.standard_invoice_number.setText(f"N° facture: {invoice_id}")

        else:
            date_value = form.date_input.date().toString("yyyy-MM-dd") if hasattr(form, "date_input") else ""
            total = body_layout.calculate_total()

            if body_layout.current_invoice_id:
                invoice_id = body_layout.invoice_service.update_proforma_invoice(
                    body_layout.current_invoice_id,
                    company_name,
                    nif,
                    stat,
                    date_value,
                    responsable,
                    total,
                    selected_products,
                )
            else:
                invoice_id = body_layout.invoice_service.save_proforma_invoice(
                    company_name,
                    nif,
                    stat,
                    date_value,
                    responsable,
                    total,
                    selected_products,
                )

        msg = QMessageBox()
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle("Enregistrement réussi")
        msg.setText(f"Enregistrement effectué avec succès.\nNuméro de facture: {invoice_id}")
        msg.exec()

        SaveInvoiceAction._refresh_record_list(main_layout, body_layout)

        # Clear form and selection, then rebuild the UI for a new invoice of the same type
        body_layout.clear_form_and_selection()
        try:
            # Rebuild the UI to show a fresh invoice view (standard or proforma)
            main_layout.build_ui(GlobalVariable.invoice_type)
        except Exception:
            # If rebuilding fails, at least ensure the current form is cleared
            pass
