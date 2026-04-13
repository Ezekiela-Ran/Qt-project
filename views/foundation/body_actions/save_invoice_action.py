from PySide6.QtWidgets import QMessageBox
from views.foundation.globals import GlobalVariable


class SaveInvoiceAction:
    @staticmethod
    def _normalize_designation_key(value):
        return " ".join(str(value or "").split()).strip().casefold()

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
        responsable = GlobalVariable.current_username()
        stat = form.stat_input.text()
        nif = form.nif_input.text()

        errors = []
        if not company_name:
            errors.append("Raison sociale est obligatoire")
        if not responsable:
            errors.append("Aucun utilisateur connecté")

        if hasattr(form, "set_responsable_username"):
            form.set_responsable_username(responsable)

        pm = body_layout.product_manager
        if hasattr(pm, "commit_active_edit") and not pm.commit_active_edit():
            return
        selected_line_items = pm.build_selected_line_items()
        if not selected_line_items:
            errors.append("Au moins un produit doit être sélectionné")

        if GlobalVariable.invoice_type == "standard":
            next_ref = int(body_layout.product_service.get_max_ref_b_analyse() or 0) + 1
            selected_line_items = pm.build_selected_line_items(
                allocate_missing_refs=True,
                start_ref=next_ref,
                persist_allocations=True,
            )

            for line_item in selected_line_items:
                if line_item.get("ref_b_analyse") is None:
                    product = body_layout.product_service.get_product_by_id(line_item.get("product_id"))
                    product_name = product["product_name"] if product else "inconnu"
                    errors.append(
                        f"Ref.b.analyse manquant pour le produit {product_name}. Désélectionnez puis resélectionnez le produit."
                    )
        else:
            selected_line_items = pm.build_selected_line_items()

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
                    selected_line_items,
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
                    selected_line_items,
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
                    selected_line_items,
                )
            else:
                invoice_id = body_layout.invoice_service.save_proforma_invoice(
                    company_name,
                    nif,
                    stat,
                    date_value,
                    responsable,
                    total,
                    selected_line_items,
                )

            if hasattr(form, "proforma_invoice_number"):
                form.proforma_invoice_number.setText(str(invoice_id))

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
