from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import Qt

from views.foundation.globals import GlobalVariable


class SaveInvoiceAction:
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

        # Persist current in-memory refs for selected products so validation uses up-to-date values
        pm = body_layout.product_manager
        if pm.invoice_type == "standard":
            try:
                db_max = int(body_layout.product_service.get_max_ref_b_analyse() or 0)
            except Exception:
                db_max = 0
            # Ensure we iterate in selection order so assigned refs are sequential
            order = pm.selection_order[:] if getattr(pm, 'selection_order', None) else list(selected_products)
            for pid in order:
                # find row for pid
                for row in range(pm.product_table.rowCount()):
                    item = pm.product_table.item(row, 0)
                    if item and item.data(Qt.UserRole) == pid:
                        ref_widget = pm.product_table.cellWidget(row, 1)
                        num_act = pm.product_table.cellWidget(row, 2).text()
                        physico = int(pm.parse_number(pm.product_table.cellWidget(row, 3).text()))
                        toxico = int(pm.parse_number(pm.product_table.cellWidget(row, 4).text()))
                        micro = int(pm.parse_number(pm.product_table.cellWidget(row, 5).text()))
                        subtotal = int((physico + toxico + micro) or 0)
                        # assign next DB-unique ref (db_max + 1, sequential)
                        db_max += 1
                        assigned = db_max
                        # update UI and persist
                        try:
                            if ref_widget:
                                ref_widget.setText(str(assigned))
                            body_layout.product_service.update_product(pid, assigned, num_act, physico, toxico, micro, subtotal, update_ref=True)
                        except Exception:
                            pass
                        break

        if GlobalVariable.invoice_type == "standard":
            for pid in selected_products:
                product = body_layout.product_service.get_product_by_id(pid)
                if not product or not product.get("ref_b_analyse") or str(product["ref_b_analyse"]).strip() == "":
                    product_name = product["product_name"] if product else "inconnu"
                    errors.append(
                        f"Le champ 'Ref.b.analyse' est obligatoire pour le produit {product_name}"
                    )

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
