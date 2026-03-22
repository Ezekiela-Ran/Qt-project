from PySide6 import QtWidgets
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import QMessageBox
from views.components.standard_invoice.product_manager import ProductManager
from models.database_manager import DatabaseManager

class BodyLayout(QtWidgets.QWidget):
    def __init__(self, parent=None, invoice_type="standard"):
        super().__init__(parent)

        # Layout principal
        self.body_layout = QtWidgets.QVBoxLayout(self)
        self.body_layout.setContentsMargins(0, 0, 0, 0)

        self.setObjectName("card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        db_manager = DatabaseManager()
        # Gestion des produits:
        self.product_manager = ProductManager(db_manager, invoice_type)
        self.product_manager.setObjectName("productType")
        self.product_manager.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        # Label pour le total
        self.net_a_payer_label = QtWidgets.QLabel("Net à payer: 0.00 Ariary (ZERO ARIARY)")
        self.net_a_payer_label.setAlignment(Qt.AlignCenter)
        self.net_a_payer_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #000000; background-color: #FFFFCC; padding: 4px; border: 1px solid #999999; border-radius: 4px;")

        # Bouton enregistrer
        self.save_button = QtWidgets.QPushButton("Enregistrer")
        self.save_button.setStyleSheet("QPushButton { background-color: #1F4E79; color: white; padding: 10px; border: none; border-radius: 5px; } QPushButton:hover { background-color: #163D62; }")

        # Bouton imprimer
        self.print_button = QtWidgets.QPushButton("Imprimer")
        self.print_button.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; padding: 10px; border: none; border-radius: 5px; } QPushButton:hover { background-color: #45a049; }")

        # Bouton convertir (pour proforma)
        self.convert_button = QtWidgets.QPushButton("Convertir")
        self.convert_button.setStyleSheet("QPushButton { background-color: #FF9800; color: white; padding: 10px; border: none; border-radius: 5px; } QPushButton:hover { background-color: #e68900; }")

        # Layout pour le total et les boutons
        bottom_layout = QtWidgets.QHBoxLayout()
        bottom_layout.addWidget(self.net_a_payer_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.save_button)
        bottom_layout.addWidget(self.print_button)
        if invoice_type == "proforma":
            bottom_layout.addWidget(self.convert_button)

        self.body_layout.addWidget(self.product_manager)
        self.body_layout.addLayout(bottom_layout)

        # ID de la facture en cours de modification (None = nouvelle facture)
        self.current_invoice_id = None

        # Connecter le signal de changement de sélection pour mettre à jour le total
        self.product_manager.selection_changed.connect(self.update_total_display)

        # Connecter le bouton
        self.save_button.clicked.connect(self.save_invoice)
        if invoice_type == "proforma":
            self.convert_button.clicked.connect(self.convert_to_standard)

    def convert_to_standard(self):
        # Récupérer les données actuelles de proforma
        main_layout = self.parent()
        if hasattr(main_layout, 'head_layout') and hasattr(main_layout.head_layout, 'form'):
            proforma_form = main_layout.head_layout.form
            selected_products = [pid for pid, sel in self.product_manager.selected_products.items() if sel]
            
            # Basculer vers standard
            main_layout.menubar_click_standard()
            
            # Pré-remplir le formulaire standard
            standard_form = main_layout.head_layout.form
            standard_form.company_name_input.setText(proforma_form.company_name_input.text())
            standard_form.responsable_input.setText(proforma_form.responsable_input.text())
            standard_form.stat_input.setText(proforma_form.stat_input.text())
            standard_form.nif_input.setText(proforma_form.nif_input.text())
            standard_form.address_input.setText(proforma_form.address_input.text())
            
            # Sélectionner les mêmes produits
            main_layout.body_layout.product_manager.select_products(selected_products)
            
            # Mettre à jour le total
            main_layout.body_layout.update_total_display()

        # Chargement du style QSS
        self._apply_stylesheet("styles/product_type.qss")

    def number_to_words(self, number):
        # Simple number to words in French
        units = ["", "UN", "DEUX", "TROIS", "QUATRE", "CINQ", "SIX", "SEPT", "HUIT", "NEUF", "DIX", "ONZE", "DOUZE", "TREIZE", "QUATORZE", "QUINZE", "SEIZE", "DIX-SEPT", "DIX-HUIT", "DIX-NEUF"]
        tens = ["", "", "VINGT", "TRENTE", "QUARANTE", "CINQUANTE", "SOIXANTE", "SOIXANTE-DIX", "QUATRE-VINGT", "QUATRE-VINGT-DIX"]
        
        if number == 0:
            return "ZERO"
        
        words = []
        if number >= 1000000:
            millions = number // 1000000
            words.append(self.number_to_words(millions) + " MILLION")
            number %= 1000000
        if number >= 1000:
            thousands = number // 1000
            words.append(self.number_to_words(thousands) + " MILLE")
            number %= 1000
        if number >= 100:
            hundreds = number // 100
            if hundreds == 1:
                words.append("CENT")
            else:
                words.append(units[hundreds] + " CENT")
            number %= 100
        if number >= 20:
            ten = number // 10
            words.append(tens[ten])
            number %= 10
            if number > 0:
                words.append(units[number])
        elif number > 0:
            words.append(units[number])
        
        return " ".join(words).strip()

    def save_invoice(self):
        # Accéder au head_layout pour récupérer les données du formulaire
        main_layout = self.parent()
        if hasattr(main_layout, 'head_layout') and hasattr(main_layout.head_layout, 'form'):
            form = main_layout.head_layout.form
            
            # Récupérer les données du formulaire
            company_name = form.company_name_input.text().strip()
            responsable = form.responsable_input.text().strip()
            stat = form.stat_input.text()
            nif = form.nif_input.text()
            
            # Validation
            errors = []
            if not company_name:
                errors.append("Raison sociale est obligatoire")
            if not responsable:
                errors.append("Responsable est obligatoire")
            selected_products = [pid for pid, sel in self.product_manager.selected_products.items() if sel]
            if not selected_products:
                errors.append("Au moins un produit doit être sélectionné")
            
            # Validation spécifique pour standard : ref.b.analyse obligatoire
            from views.foundation.globals import GlobalVariable
            if GlobalVariable.invoice_type == "standard":
                for pid in selected_products:
                    product = self.product_manager.db.get_product_by_id(pid)
                    if not product or not product.get('ref_b_analyse') or str(product['ref_b_analyse']).strip() == "":
                        errors.append(f"Le champ 'Ref.b.analyse' est obligatoire pour le produit {product['product_name'] if product else 'inconnu'}")
            
            if errors:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Critical)
                msg.setWindowTitle("Erreur de validation")
                msg.setText("L'enregistrement ne peut pas être effectué pour les raisons suivantes:")
                msg.setDetailedText("\n".join(errors))
                msg.exec()
                return
            
            # Récupérer les données spécifiques selon le type
            from views.foundation.globals import GlobalVariable
            if GlobalVariable.invoice_type == "standard":
                if hasattr(form, 'date_issue_input'):
                    date_issue = form.date_issue_input.date().toString("yyyy-MM-dd")
                else:
                    date_issue = ""
                if hasattr(form, 'date_result_input'):
                    date_result = form.date_result_input.date().toString("yyyy-MM-dd")
                else:
                    date_result = ""
                if hasattr(form, 'product_ref_input'):
                    product_ref = form.product_ref_input.text()
                else:
                    product_ref = ""
                address = form.address_input.text()

                # Calculer le total
                total = self.calculate_total()

                # Sauvegarder (update si invoice existante)
                selected_products = [pid for pid, sel in self.product_manager.selected_products.items() if sel]
                if self.current_invoice_id:
                    invoice_id = self.product_manager.db.update_standard_invoice(
                        self.current_invoice_id,
                        company_name,
                        stat,
                        nif,
                        address,
                        date_issue,
                        date_result,
                        product_ref,
                        responsable,
                        total,
                        selected_products
                    )
                else:
                    invoice_id = self.product_manager.db.save_standard_invoice(
                        company_name,
                        stat,
                        nif,
                        address,
                        date_issue,
                        date_result,
                        product_ref,
                        responsable,
                        total,
                        selected_products
                    )

                if hasattr(form, 'standard_invoice_number'):
                    form.standard_invoice_number.setText(f"N° facture: {invoice_id}")

            elif GlobalVariable.invoice_type == "proforma":
                if hasattr(form, 'date_input'):
                    date = form.date_input.date().toString("yyyy-MM-dd")
                else:
                    date = ""

                # Calculer le total
                total = self.calculate_total()

                selected_products = [pid for pid, sel in self.product_manager.selected_products.items() if sel]
                if self.current_invoice_id:
                    invoice_id = self.product_manager.db.update_proforma_invoice(
                        self.current_invoice_id,
                        company_name,
                        nif,
                        stat,
                        date,
                        responsable,
                        total,
                        selected_products
                    )
                else:
                    invoice_id = self.product_manager.db.save_proforma_invoice(
                        company_name,
                        nif,
                        stat,
                        date,
                        responsable,
                        total,
                        selected_products
                    )
            
            # Afficher popup de confirmation
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Information)
            msg.setWindowTitle("Enregistrement réussi")
            msg.setText(f"Enregistrement effectué avec succès.\nNuméro de facture: {invoice_id}")
            msg.exec()
            
            # Mettre à jour l'affichage des records
            if hasattr(main_layout.head_layout, 'record'):
                main_layout.head_layout.record.load_records()
            
            # Vider le formulaire et désélectionner les produits
            self.clear_form_and_selection()

    def calculate_total(self):
        total = 0.0
        for pid, selected in self.product_manager.selected_products.items():
            if selected:
                product = self.product_manager.db.get_product_by_id(pid)
                if product and 'subtotal' in product:
                    try:
                        total += float(product['subtotal'] or 0)
                    except (ValueError, TypeError):
                        pass
        return total

    def clear_form_and_selection(self):
        # Vider le formulaire
        main_layout = self.parent()
        if hasattr(main_layout, 'head_layout') and hasattr(main_layout.head_layout, 'form'):
            form = main_layout.head_layout.form
            form.company_name_input.clear()
            form.responsable_input.clear()
            form.stat_input.clear()
            form.nif_input.clear()
            form.address_input.clear()
            
            if hasattr(form, 'date_issue_input'):
                form.date_issue_input.setDate(QDate.currentDate())
            if hasattr(form, 'date_result_input'):
                form.date_result_input.setDate(QDate.currentDate())
            if hasattr(form, 'product_ref_input'):
                form.product_ref_input.clear()
            if hasattr(form, 'date_input'):
                form.date_input.setDate(QDate.currentDate())
        
        # Désélectionner tous les produits
        self.product_manager.clear_selection()

        # Réinitialiser l'identifiant du record sélectionné (mode nouveau enregistrement)
        self.current_invoice_id = None
        
        # Remettre le total à 0
        self.net_a_payer_label.setText("Net à payer: 0.00 Ariary (ZERO ARIARY)")

    def update_total_display(self):
        total = self.calculate_total()
        total_words = self.number_to_words(int(total)) + " ARIARY"
        formatted_total = f"{total:,.2f}".replace(",", " ")
        self.net_a_payer_label.setText(f"Net à payer: {formatted_total} Ariary ({total_words})")

    def _apply_stylesheet(self, path: str):
        """Charge et applique une feuille de style QSS depuis un fichier."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print(f"Fichier de style introuvable : {path}")

