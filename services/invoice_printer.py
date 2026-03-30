from pathlib import Path
from html import escape
import tempfile
import subprocess
import os
import platform

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from PySide6.QtWidgets import QMessageBox

from utils.text_utils import TextUtils
from utils.path_utils import resolve_resource_path


class InvoicePrinter:
    def __init__(self, parent_widget):
        self.parent = parent_widget

    @staticmethod
    def _draw_footer(canvas, doc):
        return

    @staticmethod
    def _build_payment_mode_table(styles):
        payment_table = Table(
            [[
                Paragraph("<b>Mode de paiement</b>", styles['Normal']),
                "",
                Paragraph("Espèce", styles['Normal']),
                "",
                Paragraph("Chèque", styles['Normal']),
            ]],
            colWidths=[105, 12, 55, 12, 55],
        )
        payment_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('BOX', (1,0), (1,0), 1, colors.black),
            ('BOX', (3,0), (3,0), 1, colors.black),
        ]))
        return payment_table

    def _resolve_logo_src(self):
        logo_path = resolve_resource_path("images/image.png")
        return str(logo_path) if logo_path.exists() else ""

    def _load_print_css(self):
        try:
            with open(resolve_resource_path("styles/invoice_print.css"), "r", encoding="utf-8") as css_file:
                return css_file.read()
        except FileNotFoundError:
            return ""

    def generate_invoice_html(self, form, invoice_type, selected_products, db_manager, invoice_id=None, ref_mapping=None, num_act_mapping=None):
        """Extrait les données et les stocke pour la génération PDF reportlab"""
        # Stocker les données pour utilisation ultérieure dans generate_pdf_from_html
        self._invoice_data = {
            'form': form,
            'invoice_type': invoice_type,
            'selected_products': selected_products,
            'db_manager': db_manager,
            'invoice_id': invoice_id,
            'ref_mapping': ref_mapping,
            'num_act_mapping': num_act_mapping
        }
        # Retourner un placeholder pour compatibilité
        return "<html><body>Facture générée avec reportlab</body></html>"

    def _generate_reportlab_elements(self):
        """Génère les éléments reportlab pour la facture"""
        if not hasattr(self, '_invoice_data'):
            return []
        
        data = self._invoice_data
        form = data['form']
        invoice_type = data['invoice_type']
        selected_products = data['selected_products']
        db_manager = data['db_manager']
        invoice_id = data.get('invoice_id')
        ref_mapping = data.get('ref_mapping')
        num_act_mapping = data.get('num_act_mapping') or {}
        
        # Extraire les données du formulaire
        company_name = form.company_name_input.text().strip()
        responsable = form.responsable_input.text().strip()
        stat = form.stat_input.text().strip()
        nif = form.nif_input.text().strip()
        address = form.address_input.text().strip() if hasattr(form, 'address_input') else ""
        
        if invoice_type == 'standard':
            date_issue = form.date_issue_input.date().toString('dd/MM/yyyy') if hasattr(form, 'date_issue_input') else ''
            date_result = form.date_result_input.date().toString('dd/MM/yyyy') if hasattr(form, 'date_result_input') else ''
            product_ref_raw = form.product_ref_input.text() if hasattr(form, 'product_ref_input') else ''
            title = f'FACTURE N°{invoice_id}' if invoice_id else 'FACTURE'
        else:
            date_issue = form.date_input.date().toString('dd/MM/yyyy') if hasattr(form, 'date_input') else ''
            date_result = ''
            product_ref_raw = ''
            title = 'FACTURE PROFORMA'
        
        # Récupérer les produits
        products = []
        for pid in selected_products:
            prod = db_manager.get_product_by_id(pid)
            if not prod:
                continue
            if ref_mapping and pid in ref_mapping:
                prod = dict(prod)
                prod['ref_b_analyse'] = ref_mapping.get(pid)
            if pid in num_act_mapping:
                if not isinstance(prod, dict):
                    prod = dict(prod)
                prod['num_act'] = num_act_mapping.get(pid)
            products.append(prod)
        
        total = sum(float(p.get('subtotal', 0) or 0) for p in products)
        total_formatted = f"{total:,.0f}".replace(',', ' ')
        total_words = TextUtils.number_to_words(round(total)).upper()
        
        # Créer les styles
        styles = getSampleStyleSheet()
        titre_style = ParagraphStyle(
            name="TitreCentree",
            parent=styles['Normal'],
            fontSize=11,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        signature_note_style = ParagraphStyle(
            name="SignatureNote",
            parent=styles['Normal'],
            fontSize=9,
            alignment=TA_CENTER,
            leading=11,
        )
        
        elements = []
        logo_path = self._resolve_logo_src()
        
        # HEADER AVEC LOGO ET AGENCE
        try:
            logo = Image(logo_path, width=100, height=80)
        except:
            logo = None
        
        # Titre dans le header
        titre = Paragraph(
            "<b>AGENCE DE CONTRÔLE DE<br/>LA SECURITE SANITAIRE<br/>ET DE LA QUALITE DES<br/>DENREES ALIMENTAIRES</b>",
            titre_style
        )
        
        # Tableau DOIT (droite)
        right_header = [
            ["DOIT"],
            [f"Raison social: {company_name}"],
            [f"Statistique: {stat}"],
            [f"NIF: {nif}"],
            [f"Adresse: {address}"],
        ]
        
        right_table = Table(right_header)
        right_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ]))
        
        # Tableau GAUCHE (agence + titre)
        left_header = [
            [logo if logo else "", titre, "", right_table],
            [""],
            ["NIF: 2001451249"],
            ["STAT: 86,909,112,006,001,800"],
            ["TEL: 22 222 39"],
            ["Adresse: Rue Karidja Tsaralalàna"],
        ]
        
        left_table = Table(left_header, colWidths=[100, 150, 50, 200])
        left_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1),'TOP'),
            ('LEFTPADDING', (0,0), (0,0), 0),
            ('RIGHTPADDING', (0,0), (0,0), 10),
            ('TOPPADDING', (1,0), (1,0), 10),
            ('BOX', (3,0), (3,0), 0.5, colors.black),
            ('LINEABOVE', (1,0), (1,0), 1, colors.black),
            ('LINEBELOW', (1,0), (1,0), 1, colors.black),   
        ]))
        
        header_main = Table([[left_table]])
        elements.append(header_main)
        elements.append(Spacer(1, 20))
        
        # TITLE
        title_para = Paragraph(f"<b>{title}</b>", titre_style)
        elements.append(title_para)
        elements.append(Spacer(1, 10))
        
        # METADATA TABLE
        if invoice_type == 'standard':
            metadata_data = [
                [f"Date d'émission: {date_issue}", f"Référence produits: {product_ref_raw}", f"Date résultat: {date_result}", f"Responsable: {responsable}"]
            ]
        else:
            metadata_data = [
                [f"Date: {date_issue}", f"Responsable: {responsable}"]
            ]
        
        metadata_table = Table(metadata_data)
        metadata_table.setStyle(TableStyle([
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
        ]))
        elements.append(metadata_table)
        elements.append(Spacer(1, 10))
        
        # PRODUCTS TABLE
        page_width = A4[0] - 60  # (30 marge gauche + 30 droite)

        if invoice_type == 'standard':
            header_row = ['Réf. Bulletin', 'Désignations', 'N°Acte', 'Physico', 'Micro', 'Toxico', 'Sous-total']
            data_rows = [header_row]
            for prod in products:
                data_rows.append([
                    str(prod.get('ref_b_analyse', '') or ''),
                    str(prod.get('product_name', '') or ''),
                    str(prod.get('num_act', '') or ''),
                    str(prod.get('physico', '') or ''),
                    str(prod.get('micro', '') or ''),
                    str(prod.get('toxico', '') or ''),
                    str(prod.get('subtotal', '') or ''),
                ])
            data_rows.append(['', '', '', '', '', 'Montant à payer', total_formatted + ' Ar'])
            col_widths = [
                page_width * 0.12,
                page_width * 0.22,
                page_width * 0.12,
                page_width * 0.11,
                page_width * 0.11,
                page_width * 0.11,
                page_width * 0.21,
            ]
            total_span_end = -3
        else:
            header_row = ['Désignations', 'Physico', 'Micro', 'Toxico', 'Sous-total']
            data_rows = [header_row]
            for prod in products:
                data_rows.append([
                    str(prod.get('product_name', '') or ''),
                    str(prod.get('physico', '') or ''),
                    str(prod.get('micro', '') or ''),
                    str(prod.get('toxico', '') or ''),
                    str(prod.get('subtotal', '') or ''),
                ])
            data_rows.append(['', '', '', 'Montant à payer', total_formatted + ' Ar'])
            col_widths = [
                page_width * 0.32,
                page_width * 0.16,
                page_width * 0.16,
                page_width * 0.16,
                page_width * 0.20,
            ]
            total_span_end = -2
        
        products_table = Table(
            data_rows,
            colWidths=col_widths
        )
        
        products_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,-1), (-1,-1), colors.beige),

            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('ALIGN', (0,1), (-1,-2), 'CENTER'),

            ('BACKGROUND', (0,-1), (-1,-1), colors.beige),

            ('SPAN', (0,-1), (total_span_end,-1)),
            ('ALIGN', (-2,-1), (-2,-1), 'RIGHT'),
            ('FONTNAME', (-1,-1), (-1,-1), 'Helvetica-Bold'),
            ('ALIGN', (-1,-1), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-2), 1, colors.black),
            
        ]))
        elements.append(products_table)
        elements.append(Spacer(1, 20))
        
        # FOOTER
        footer_text = f"Arrêtée la présente facture à la somme de: {total_words} ARIARY"
        footer_para = Paragraph(f"<b>{footer_text}</b>", styles['Normal'])
        elements.append(footer_para)
        elements.append(Spacer(1, 10))
        elements.append(self._build_payment_mode_table(styles))
        elements.append(Spacer(1, 24))
        
        # Zone de signature avec mentions en dessous des intitulés.
        sig_table = Table([
            ['Le Client', 'Le(a) Caissier(e)'],
            [
                Paragraph("(*) Chèque vise à l'ordre de Madame le RECEVEUR GENERAL .", signature_note_style),
                Paragraph("Quittance", signature_note_style),
            ],
        ], colWidths=[page_width * 0.5, page_width * 0.5])
        sig_table.setStyle(TableStyle([
            ('LEFTPADDING', (0,0), (-1,-1), 12),
            ('RIGHTPADDING', (0,0), (-1,-1), 12),
            ('TOPPADDING', (0,0), (-1,0), 0),
            ('BOTTOMPADDING', (0,0), (-1,0), 0),
            ('TOPPADDING', (0,1), (-1,1), 52),
            ('BOTTOMPADDING', (0,1), (-1,1), 0),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
        ]))
        elements.append(sig_table)
        
        return elements

    def generate_pdf_from_html(self, html, output_path):
        """Génère le PDF avec reportlab"""
        try:
            elements = self._generate_reportlab_elements()
            if not elements:
                QMessageBox.critical(self.parent, 'Erreur', 'Impossible de générer les éléments PDF')
                return False
            
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                leftMargin=30,
                rightMargin=30,
                topMargin=30,
                bottomMargin=52
            )
            doc.build(elements, onFirstPage=self._draw_footer, onLaterPages=self._draw_footer)
            return True
        except Exception as e:
            QMessageBox.critical(self.parent, 'Erreur', f'Erreur lors de la génération du PDF: {str(e)}')
            return False



    def preview_invoice(self, html):
        if not html:
            QMessageBox.warning(self.parent, 'Aperçu impossible', 'Impossible de générer l\'aperçu. Vérifiez les données.')
            return

        try:
            # Créer un fichier PDF temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_path = tmp_file.name

            # Générer le PDF
            if not self.generate_pdf_from_html(html, tmp_path):
                return

            # Ouvrir le PDF avec le visionneur par défaut (cross-platform)
            self._open_file_with_default_app(tmp_path)
            
        except Exception as e:
            QMessageBox.critical(self.parent, 'Erreur', f'Erreur lors de l\'aperçu: {str(e)}')

    def print_invoice(self, html):
        if not html:
            QMessageBox.warning(self.parent, 'Impression impossible', 'Impossible de générer l\'impression. Vérifiez les données.')
            return

        try:
            # Créer un fichier PDF temporaire
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_path = tmp_file.name

            # Générer le PDF
            if not self.generate_pdf_from_html(html, tmp_path):
                return

            # Lancer l'impression avec la commande système adaptée (cross-platform)
            self._print_file(tmp_path)
            QMessageBox.information(self.parent, 'Impression', 'Document envoyé à l\'imprimante.')
            
        except Exception as e:
            QMessageBox.critical(self.parent, 'Erreur', f'Erreur lors de l\'impression: {str(e)}')

    def _open_file_with_default_app(self, path):
        system_name = platform.system()
        if system_name == 'Windows':
            os.startfile(path)
            return
        if system_name == 'Darwin':
            subprocess.Popen(['open', path])
            return
        subprocess.Popen(['xdg-open', path])

    def _print_file(self, path):
        system_name = platform.system()
        if system_name == 'Windows':
            os.startfile(path, 'print')
            return
        if system_name == 'Darwin':
            subprocess.Popen(['lp', path])
            return
        subprocess.Popen(['lp', path])
