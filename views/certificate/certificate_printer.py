"""
Génération HTML et impression des certificats CC / CNC.

Chaque certificat occupe une page A4 portrait.
L'impression utilise QPrinter / QPrintDialog (même approche que InvoicePrinter).
"""
from datetime import date
import os
from pathlib import Path
import tempfile
from html import escape
from urllib.parse import unquote, urlparse

from PySide6.QtCore import QSize, Qt, QRectF
from PySide6.QtGui import QTextDocument, QPainter, QPageSize, QPageLayout
from PySide6.QtPrintSupport import QPrinter, QPrintDialog
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtPdf import QPdfDocument
from utils.path_utils import resolve_resource_path


_TITLES = {
    "CC":  "CERTIFICAT DE CONSOMMABILITÉ",
    "CNC": "CERTIFICAT DE NON CONSOMMABILITÉ",
}


class CertificatePrinter:
    """
    Convertit une liste d'assignations (pid, product_name, cert_type)
    en HTML imprimable et lance le dialogue d'impression.
    """

    def __init__(self, parent_widget):
        self.parent = parent_widget

    # ------------------------------------------------------------------
    # Ressources
    # ------------------------------------------------------------------

    def _resolve_logo_sources(self) -> dict:
        mapping = {
            "left": resolve_resource_path("images/unnamed.png"),
            "center": resolve_resource_path("images/unnamed-1.png"),
            "right": resolve_resource_path("images/image.png"),
        }
        return {
            key: path.as_uri() if path.exists() else ""
            for key, path in mapping.items()
        }

    @staticmethod
    def _uri_to_local_path(path_or_uri: str) -> str:
        text = str(path_or_uri or "").strip()
        if not text:
            return ""
        if not text.startswith("file://"):
            return text

        parsed = urlparse(text)
        local_path = unquote(parsed.path or "")
        if local_path.startswith("/") and len(local_path) > 2 and local_path[2] == ":":
            local_path = local_path[1:]
        return local_path

    def _load_css(self) -> str:
        try:
            with open(resolve_resource_path("styles/certificate_print.css"), "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    # ------------------------------------------------------------------
    # Extraction des données du formulaire
    # ------------------------------------------------------------------

    def _extract_form_data(self, form) -> dict:
        """Lit les champs du formulaire client actif et échappe les valeurs HTML."""
        if hasattr(form, "date_issue_input"):
            date_str = form.date_issue_input.date().toString("dd/MM/yyyy")
        elif hasattr(form, "date_input"):
            date_str = form.date_input.date().toString("dd/MM/yyyy")
        else:
            date_str = ""

        return {
            "company_name": escape(form.company_name_input.text().strip()),
            "responsable":  escape(form.responsable_input.text().strip()),
            "stat":         escape(form.stat_input.text().strip()),
            "nif":          escape(form.nif_input.text().strip()),
            "address":      escape(
                form.address_input.text().strip() if hasattr(form, "address_input") else ""
            ),
            "date":         escape(date_str),
            "date_result":  escape(
                form.date_result_input.date().toString("dd/MM/yyyy")
                if hasattr(form, "date_result_input") else ""
            ),
            "product_ref":  escape(
                form.product_ref_input.text().strip()
                if hasattr(form, "product_ref_input") else ""
            ),
        }

    @staticmethod
    def _build_proces_verbal(num_acte: str, num_prl: str, date_commerce: str, year_two_digits: str) -> str:
        reference = ""
        if num_acte:
            reference = f"N°{num_acte}-{year_two_digits}/MIC/SG/DGC/DPC/PRL"
        elif year_two_digits:
            reference = f"N°-{year_two_digits}/MIC/SG/DGC/DPC/PRL"

        if num_prl:
            reference = f"{reference} {num_prl}".strip()
        if date_commerce:
            return f"{reference} du {date_commerce}".strip()
        return reference.strip()

    @staticmethod
    def _build_reference(ref_b_analyse: str, date_issue: str, invoice_number: str, year_two_digits: str) -> str:
        parts = []
        if ref_b_analyse or year_two_digits:
            parts.append(f"N°{ref_b_analyse}/{year_two_digits}" if ref_b_analyse else f"N°/{year_two_digits}")
        if date_issue:
            parts.append(f"du {date_issue}")
        if invoice_number:
            parts.append(f"Facture N°{invoice_number}/{year_two_digits}/ACSSQDA")
        return " ".join(part for part in parts if part).strip()

    @staticmethod
    def _display_date(value: str) -> str:
        text = str(value or "").strip()
        return text or "-"

    # ------------------------------------------------------------------
    # Génération HTML
    # ------------------------------------------------------------------

    def _render_single_certificate(
        self,
        cert_type: str,
        product_name: str,
        fd: dict,
        logos: dict,
        is_last: bool,
        extras: dict | None = None,
    ) -> str:
        """
        Génère le fragment HTML d'un seul certificat.

        Paramètres
        ----------
        cert_type    : 'CC' ou 'CNC'
        product_name : désignation du produit
        fd           : dict des données client (clés: company_name, nif, …)
        logos        : dictionnaire des logos d'entête
        is_last      : True pour le dernier certificat (pas de saut de page final)
        extras       : dict optionnel avec les clés quantite, quantite_analysee,
                       num_lot, num_acte, analyse
        """
        if extras is None:
            extras = {}

        title      = escape(_TITLES[cert_type])
        desig      = escape(product_name)
        page_break = "auto" if is_last else "always"

        quantite          = escape(extras.get("quantite", ""))
        quantite_analysee = escape(extras.get("quantite_analysee", ""))
        num_lot           = escape(extras.get("num_lot", ""))
        num_acte          = escape(extras.get("num_acte", ""))
        analyse_raw       = extras.get("analyse", "")
        classe            = escape(extras.get("classe", ""))
        date_production   = escape(self._display_date(extras.get("date_production", "")))
        date_peremption   = escape(self._display_date(extras.get("date_peremption", "")))
        num_cert          = escape(extras.get("num_cert", ""))
        num_prl           = escape(extras.get("num_prl", ""))
        date_commerce     = escape(self._display_date(extras.get("date_commerce", "")))
        reference         = escape(extras.get("reference", ""))
        ref_b_analyse     = escape(str(extras.get("ref_b_analyse", "") or ""))
        invoice_number    = escape(str(extras.get("invoice_number", "") or ""))

        analyse_sentence = self._build_analysis_sentence(analyse_raw)
        result_text = "consommable" if cert_type == "CC" else "non consommable"
        year_two_digits = date.today().strftime("%y")
        header_number = f"N°/{year_two_digits}MSANP/SG/ACSSQDA/{cert_type}"
        if num_cert:
            header_number = f"N°{num_cert}/{year_two_digits}MSANP/SG/ACSSQDA/{cert_type}"

        proces_verbal = escape(
            self._build_proces_verbal(
                extras.get("num_acte", ""),
                extras.get("num_prl", ""),
                extras.get("date_commerce", ""),
                year_two_digits,
            )
        )

        if not reference:
            reference = escape(
                self._build_reference(
                    extras.get("ref_b_analyse", ""),
                    fd["date"],
                    extras.get("invoice_number", ""),
                    year_two_digits,
                )
            )

        left_logo = (
            f'<img src="{logos.get("left", "")}" style="width:44px;height:44px;object-fit:contain;">'
            if logos.get("left")
            else ""
        )
        center_logo = (
            f'<img src="{logos.get("center", "")}" style="width:104px;height:36px;object-fit:contain;">'
            if logos.get("center")
            else ""
        )
        right_logo = (
            f'<img src="{logos.get("right", "")}" style="width:60px;height:50px;object-fit:contain;">'
            if logos.get("right")
            else ""
        )

        return f"""
    <div style="page-break-after:{page_break};padding:8pt 12pt 6pt 12pt;
          font-family:'Times New Roman',serif;font-size:10.3pt;color:#000;">

      <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:4pt;">
    <tr>
      <td width="20%" style="text-align:left;vertical-align:middle;">{left_logo}</td>
      <td width="60%" style="text-align:center;vertical-align:middle;">{center_logo}</td>
      <td width="20%" style="text-align:right;vertical-align:middle;">{right_logo}</td>
    </tr>
  </table>

  <p style="text-align:center;font-size:11.2pt;line-height:1.15;margin:0;">MINISTÈRE DE LA SANTÉ PUBLIQUE</p>
  <p style="text-align:center;font-size:10pt;line-height:1.0;margin:0;">--------------</p>
  <p style="text-align:center;font-size:11.2pt;line-height:1.15;margin:0;">SECRÉTARIAT GÉNÉRAL</p>
  <p style="text-align:center;font-size:10pt;line-height:1.0;margin:0;">--------------</p>
  <p style="text-align:center;font-size:12pt;line-height:1.2;margin:1pt 0 8pt 0;">
    AGENCE DE CONTRÔLE DE LA SÉCURITÉ SANITAIRE<br>
    ET DE LA QUALITÉ DES DENRÉES ALIMENTAIRES
  </p>

    <div style="text-align:center;margin:1pt 0 6pt 0;">
        <p style="font-size:17.5pt;font-weight:700;line-height:1.0;letter-spacing:0.05pt;margin:0;">
            {title}
        </p>
        <p style="font-size:12.8pt;font-weight:700;line-height:1.0;margin:2pt 0 0 0;">
            {escape(header_number)}
        </p>
    </div>

  <p style="line-height:1.35;margin-bottom:6pt;font-size:10.8pt;font-weight:bold;">
    Je, soussigné, le Directeur de l'Agence de Contrôle de la Sécurité Sanitaire et de la
    Qualité des Denrées Alimentaires (ACSSQDA), certifie que
  </p>

  <table width="100%" cellspacing="0" cellpadding="2" border="0" style="font-size:10.8pt;line-height:1.2;">
    <tr><td width="24%"><b>Echantillon</b></td><td width="2%">:</td><td><b>{desig}</b></td></tr>
    <tr><td><b>Classe</b></td><td>:</td><td><b>{classe}</b></td></tr>
    <tr><td><b>Quantité</b></td><td>:</td><td><b>{quantite}</b>  <span style="display:inline-block;width:24pt;"></span>
      <b>Quantité Analysée</b> : <b>{quantite_analysee}</b></td></tr>
    <tr><td><b>N° Certificat</b></td><td>:</td><td><b>{num_cert}</b></td></tr>
    <tr><td><b>N° Acte</b></td><td>:</td><td><b>{num_acte}</b></td></tr>
    <tr><td><b>Date de production</b></td><td>:</td><td><b>{date_production}</b></td></tr>
    <tr><td><b>Date de péremption</b></td><td>:</td><td><b>{date_peremption}</b></td></tr>
    <tr><td><b>Lot</b></td><td>:</td><td><b>{num_lot}</b></td></tr>
    <tr><td><b>Date commerce</b></td><td>:</td><td><b>{date_commerce}</b></td></tr>
    <tr><td><b>Procès-verbal de prélèvement</b></td><td>:</td><td><b>{proces_verbal}</b></td></tr>
    <tr><td><b>Société / Etablissement</b></td><td>:</td><td><b>{fd['company_name']}</b></td></tr>
    <tr><td><b>Responsable</b></td><td>:</td><td><b>{fd['responsable']}</b></td></tr>
    <tr><td><b>Statistique</b></td><td>:</td><td><b>{fd['stat']}</b></td></tr>
    <tr><td><b>NIF</b></td><td>:</td><td><b>{fd['nif']}</b></td></tr>
    <tr><td><b>Adresse</b></td><td>:</td><td><b>{fd['address']}</b></td></tr>
    <tr><td><b>Date d'émission</b></td><td>:</td><td><b>{fd['date']}</b></td></tr>
    <tr><td><b>Date de résultat</b></td><td>:</td><td><b>{fd['date_result']}</b></td></tr>
    <tr><td><b>Ref produit</b></td><td>:</td><td><b>{fd['product_ref']}</b></td></tr>
    <tr><td><b>Analyse</b></td><td>:</td><td><b>{escape(analyse_sentence)}</b></td></tr>
    <tr><td><b>Référence</b></td><td>:</td><td><b>{reference}</b></td></tr>
  </table>

  <p style="margin-top:8pt;font-size:11.2pt;font-weight:bold;line-height:1.3;">
    Est déclaré {result_text} à la consommation humaine
  </p>

  <p style="margin-top:5pt;font-size:10.8pt;font-weight:bold;line-height:1.3;">
    En foi de quoi, ce certificat est délivré pour servir et valoir ce que de droit.
  </p>

  <p style="text-align:right;margin-top:8pt;font-size:10.8pt;font-weight:bold;">
    Fait à Antananarivo, le {fd['date']}
  </p>

  <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:4pt;">
    <tr>
      <td width="58%"></td>
      <td width="42%" style="text-align:center;font-size:12.5pt;font-weight:bold;">Le Directeur,</td>
    </tr>
  </table>

  <p style="margin-top:56pt;font-style:italic;font-size:9.6pt;">
    *Ce certificat est valable uniquement pour le LOT ayant fait l'objet d'analyse mentionnée ci-dessus
  </p>

</div>
"""

    @staticmethod
    def _build_analysis_sentence(analyse_raw: str) -> str:
        text = str(analyse_raw or "").strip().lower()
        if not text:
            return ""
        return text

    def generate_html(self, form, assignments: list[tuple]) -> str:
        """
        Assemble le document HTML complet (tous les certificats, un par page).

        Paramètres
        ----------
        form        : formulaire client actif
        assignments : liste de (pid, product_name, cert_type)
        """
        logos = self._resolve_logo_sources()

        fd  = self._extract_form_data(form)
        css = self._load_css()

        pages = []
        for i, entry in enumerate(assignments):
            pid, product_name, cert_type = entry[0], entry[1], entry[2]
            extras = entry[3] if len(entry) > 3 else {}
            pages.append(
                self._render_single_certificate(
                    cert_type, product_name, fd, logos,
                    i == len(assignments) - 1, extras,
                )
            )

        return (
            f"<!DOCTYPE HTML><html>"
            f"<head><meta charset='UTF-8'><style>{css}</style></head>"
            f"<body>{''.join(pages)}</body></html>"
        )

    def _build_document(self, html: str) -> QTextDocument:
        document = QTextDocument(self.parent)
        document.setDocumentMargin(0)
        document.setHtml(html)
        return document

    def _generate_pdf_with_reportlab(self, form, assignments: list[tuple], output_path: str):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
            from reportlab.lib.units import mm
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image, PageBreak
            from reportlab.lib import colors

            fd = self._extract_form_data(form)
            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=16 * mm,
                leftMargin=16 * mm,
                topMargin=10 * mm,
                bottomMargin=14 * mm,
            )
            story = []
            styles = getSampleStyleSheet()
            logos = self._resolve_logo_sources()

            base_style = ParagraphStyle(
                'CertificateBase',
                parent=styles['Normal'],
                fontName='Times-Roman',
                fontSize=9.9,
                leading=13,
            )
            center_style = ParagraphStyle(
                'CertificateCenter',
                parent=base_style,
                alignment=TA_CENTER,
                leading=12,
            )
            title_style = ParagraphStyle(
                'CertificateTitle',
                parent=center_style,
                fontName='Times-Bold',
                fontSize=16.0,
                leading=16,
                spaceAfter=1,
            )
            title_sub_style = ParagraphStyle(
                'CertificateTitleSub',
                parent=center_style,
                fontName='Times-Bold',
                fontSize=12.1,
                leading=13,
            )
            intro_style = ParagraphStyle(
                'CertificateIntro',
                parent=base_style,
                fontName='Times-Bold',
                fontSize=9.4,
                leading=14,
                alignment=TA_JUSTIFY,
            )
            label_style = ParagraphStyle(
                'CertificateLabel',
                parent=base_style,
                fontName='Times-Bold',
                fontSize=9.1,
                leading=13,
            )
            value_style = ParagraphStyle(
                'CertificateValue',
                parent=base_style,
                fontName='Times-Bold',
                fontSize=9.1,
                leading=13,
            )
            declaration_style = ParagraphStyle(
                'CertificateDeclaration',
                parent=base_style,
                fontName='Times-Bold',
                fontSize=9.4,
                leading=14,
            )
            date_style = ParagraphStyle(
                'CertificateDate',
                parent=base_style,
                fontName='Times-Bold',
                fontSize=9.2,
                leading=13,
                alignment=TA_RIGHT,
            )
            director_style = ParagraphStyle(
                'CertificateDirector',
                parent=center_style,
                fontName='Times-Bold',
                fontSize=9.7,
                leading=13,
            )
            note_style = ParagraphStyle(
                'CertificateNote',
                parent=base_style,
                fontName='Times-Italic',
                fontSize=8.7,
                leading=12,
            )

            logo_height = 52

            def get_logo(path_key, max_width):
                path = logos.get(path_key, "")
                path = self._uri_to_local_path(path)

                if path and Path(path).exists():
                    img = Image(path)
                    ratio = img.imageWidth / img.imageHeight
                    img.drawHeight = logo_height
                    img.drawWidth = logo_height * ratio

                    if img.drawWidth > max_width:
                        img.drawWidth = max_width
                        img.drawHeight = max_width / ratio
                    return img
                return Spacer(1, logo_height)

            def build_header_table():
                left_logo = get_logo("left", 34 * mm)
                center_logo = get_logo("center", 30 * mm)
                right_logo = get_logo("right", 34 * mm)

                center_content = [
                    center_logo,
                    Spacer(1, 2),
                    Paragraph("<b>MINISTÈRE DE LA SANTÉ PUBLIQUE</b>", center_style),
                    Paragraph("----------------", center_style),
                    Paragraph("<b>SECRÉTARIAT GÉNÉRAL</b>", center_style),
                    Paragraph("----------------", center_style),
                    Paragraph(
                        "<b>AGENCE DE CONTRÔLE DE LA SÉCURITÉ SANITAIRE<br/>ET DE LA QUALITÉ DES DENRÉES ALIMENTAIRES</b>",
                        center_style,
                    ),
                ]

                table = Table(
                    [[left_logo, center_content, right_logo]],
                    colWidths=[doc.width * 0.18, doc.width * 0.64, doc.width * 0.18],
                )

                table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('ALIGN', (0,0), (0,0), 'LEFT'),
                    ('ALIGN', (1,0), (1,0), 'CENTER'),
                    ('ALIGN', (2,0), (2,0), 'RIGHT'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                    ('TOPPADDING', (0,0), (-1,-1), 0),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ]))

                return table

            def build_value_table(product_name, cert_type, extras):
                year_two_digits = date.today().strftime("%y")
                num_acte = str(extras.get("num_acte", "") or "").strip()
                num_prl = str(extras.get("num_prl", "") or "").strip()
                date_commerce = str(extras.get("date_commerce", "") or "").strip()
                proces_verbal = self._build_proces_verbal(num_acte, num_prl, date_commerce, year_two_digits)
                reference = extras.get("reference") or self._build_reference(
                    str(extras.get("ref_b_analyse", "") or "").strip(),
                    fd["date"],
                    str(extras.get("invoice_number", "") or "").strip(),
                    year_two_digits,
                )
                quantity_value = (
                    f"{escape(str(extras.get('quantite', '') or ''))}"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                    f"<b>Quantité Analysée</b> : {escape(str(extras.get('quantite_analysee', '') or ''))}"
                )
                rows = [
                    [Paragraph("Echantillon", label_style), Paragraph(":", label_style), Paragraph(escape(str(product_name or "")), value_style)],
                    [Paragraph("Classe", label_style), Paragraph(":", label_style), Paragraph(escape(str(extras.get('classe', '') or '')), value_style)],
                    [Paragraph("Quantité", label_style), Paragraph(":", label_style), Paragraph(quantity_value, value_style)],
                    [Paragraph("N° Acte", label_style), Paragraph(":", label_style), Paragraph(escape(num_acte), value_style)],
                    [Paragraph("Date de production", label_style), Paragraph(":", label_style), Paragraph(escape(self._display_date(str(extras.get('date_production', '') or ''))), value_style)],
                    [Paragraph("Date de péremption", label_style), Paragraph(":", label_style), Paragraph(escape(self._display_date(str(extras.get('date_peremption', '') or ''))), value_style)],
                    [Paragraph("Lot", label_style), Paragraph(":", label_style), Paragraph(escape(str(extras.get('num_lot', '') or '')), value_style)],
                    [Paragraph("Date commerce", label_style), Paragraph(":", label_style), Paragraph(escape(self._display_date(date_commerce)), value_style)],
                    [Paragraph("Procès-verbal de prélèvement", label_style), Paragraph(":", label_style), Paragraph(escape(proces_verbal), value_style)],
                    [Paragraph("Société / Etablissement", label_style), Paragraph(":", label_style), Paragraph(fd['company_name'], value_style)],
                    [Paragraph("Analyse", label_style), Paragraph(":", label_style), Paragraph(escape(str(extras.get('analyse', '') or '')), value_style)],
                    [Paragraph("Référence", label_style), Paragraph(":", label_style), Paragraph(escape(reference), value_style)],
                ]

                table = Table(rows, colWidths=[54 * mm, 5 * mm, doc.width - (59 * mm)])
                table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('ALIGN', (0,0), (1,-1), 'LEFT'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                    ('TOPPADDING', (0,0), (-1,-1), 1),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ]))
                return table

            for index, entry in enumerate(assignments):
                product_name, cert_type = entry[1], entry[2]
                extras = entry[3] if len(entry) > 3 else {}
                year_two_digits = date.today().strftime("%y")
                num_cert = str(extras.get("num_cert", "") or "").strip()
                header_number = f"N°{num_cert}/{year_two_digits}MSANP/SG/ACSSQDA/{cert_type}" if num_cert else f"N°/{year_two_digits}MSANP/SG/ACSSQDA/{cert_type}"

                story.append(build_header_table())
                story.append(Spacer(1, 6))
                story.append(Paragraph(_TITLES[cert_type], title_style))
                story.append(Paragraph(header_number, title_sub_style))
                story.append(Spacer(1, 8))
                story.append(
                    Paragraph(
                        "Je, soussigné, le Directeur de l'Agence de Contrôle de la Sécurité Sanitaire et de la Qualité des Denrées Alimentaires (ACSSQDA), certifie que",
                        intro_style,
                    )
                )
                story.append(Spacer(1, 6))
                story.append(build_value_table(product_name, cert_type, extras))
                story.append(Spacer(1, 10))

                result_text = "consommable" if cert_type == "CC" else "non consommable"
                story.append(Paragraph(f"Est déclaré {result_text} à la consommation humaine", declaration_style))
                story.append(Spacer(1, 7))
                story.append(Paragraph("En foi de quoi, ce certificat est délivré pour servir et valoir ce que de droit.", declaration_style))
                story.append(Spacer(1, 12))
                story.append(Paragraph(f"Fait à Antananarivo, le {fd['date']}", date_style))
                story.append(Spacer(1, 12))
                signature_table = Table(
                    [["", Paragraph("Le Directeur,", director_style)]],
                    colWidths=[doc.width * 0.58, doc.width * 0.42],
                )
                signature_table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('ALIGN', (1,0), (1,0), 'CENTER'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                    ('TOPPADDING', (0,0), (-1,-1), 0),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ]))
                story.append(signature_table)
                story.append(Spacer(1, 38))
                story.append(Paragraph("*Ce certificat est valable uniquement pour le LOT ayant fait l'objet d'analyse mentionnée ci-dessus", note_style))

                if index < len(assignments) - 1:
                    story.append(PageBreak())

            doc.build(story)
        except Exception:
            raise

    def _print_pdf_to_printer(self, pdf_path: str, printer: QPrinter):
        document = QPdfDocument(self.parent)
        document.load(pdf_path)
        if document.status() != QPdfDocument.Status.Ready or document.pageCount() == 0:
            raise RuntimeError("Impossible de charger le PDF généré pour l'impression.")

        painter = QPainter(printer)
        if not painter.isActive():
            raise RuntimeError("Impossible d'initialiser l'impression sur le périphérique sélectionné.")

        try:
            # Use device pixels for both rendering and drawing. Using typographic points
            # on a high-DPI printer shrinks the output into the top-left corner.
            page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
            target_width = max(1, int(page_rect.width()))
            target_height = max(1, int(page_rect.height()))

            for page_index in range(document.pageCount()):
                if page_index > 0:
                    printer.newPage()

                image = document.render(page_index, QSize(target_width, target_height))
                if image.isNull():
                    raise RuntimeError(f"Impossible de rendre la page {page_index + 1} du certificat.")

                scaled_size = image.size()
                scaled_size.scale(target_width, target_height, Qt.AspectRatioMode.KeepAspectRatio)
                draw_x = page_rect.x() + (page_rect.width() - scaled_size.width()) / 2
                draw_y = page_rect.y() + (page_rect.height() - scaled_size.height()) / 2
                target_rect = QRectF(draw_x, draw_y, scaled_size.width(), scaled_size.height())
                painter.drawImage(target_rect, image)
        finally:
            painter.end()

    # ------------------------------------------------------------------
    # Impression
    # ------------------------------------------------------------------

    def print_certificates(self, form, assignments: list[tuple]):
        """Imprime avec choix du périphérique tout en conservant le rendu ReportLab identique sur tous les OS."""
        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Portrait)

        dialog = QPrintDialog(printer, self.parent)
        dialog.setWindowTitle("Imprimer le certificat")
        if dialog.exec() != QPrintDialog.Accepted:
            return

        try:
            if printer.outputFormat() == QPrinter.OutputFormat.PdfFormat:
                file_path = printer.outputFileName()
                if not file_path:
                    default_name = f"certificat_{date.today().strftime('%Y%m%d')}.pdf"
                    file_path, _ = QFileDialog.getSaveFileName(
                        self.parent,
                        "Enregistrer le certificat en PDF",
                        default_name,
                        "PDF Files (*.pdf)",
                    )
                    if not file_path:
                        return
                if not file_path.lower().endswith('.pdf'):
                    file_path += '.pdf'

                self._generate_pdf_with_reportlab(form, assignments, file_path)
                QMessageBox.information(
                    self.parent,
                    "PDF enregistré",
                    f"Certificat enregistré dans :\n{file_path}",
                )
                return

            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                tmp_path = tmp_file.name

            try:
                self._generate_pdf_with_reportlab(form, assignments, tmp_path)
                self._print_pdf_to_printer(tmp_path, printer)
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        except Exception as e:
            QMessageBox.critical(self.parent, "Erreur", f"Erreur lors de l'impression du certificat : {e}")
