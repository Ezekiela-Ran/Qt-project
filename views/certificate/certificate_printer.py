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
      base = Path(__file__).resolve().parent.parent.parent / "images"
      mapping = {
        "left": base / "unnamed.png",
        "center": base / "unnamed-1.png",
        "right": base / "image.png",
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
            with open("styles/certificate_print.css", "r", encoding="utf-8") as f:
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
        }

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
        date_production   = escape(extras.get("date_production", ""))
        date_peremption   = escape(extras.get("date_peremption", ""))
        num_cert          = escape(extras.get("num_cert", ""))
        num_prelevement   = escape(extras.get("num_prelevement", ""))
        date_pv           = escape(extras.get("date_pv", ""))
        reference         = escape(extras.get("reference", ""))

        analyse_sentence = self._build_analysis_sentence(analyse_raw)
        result_text = "consommable" if cert_type == "CC" else "non consommable"
        year_two_digits = date.today().strftime("%y")
        header_number = f"N°/{year_two_digits}MSANP/SG/ACSSQDA/{cert_type}"
        if num_cert:
          header_number = f"N°{num_cert}/{year_two_digits}MSANP/SG/ACSSQDA/{cert_type}"

        proces_verbal = ""
        if num_prelevement and date_pv:
          proces_verbal = f"N°{num_prelevement}/{year_two_digits}/MIC/SG/DGC/DPC/PRL du {date_pv}"
        elif num_prelevement:
          proces_verbal = f"N°{num_prelevement}/{year_two_digits}/MIC/SG/DGC/DPC/PRL"
        elif date_pv:
          proces_verbal = date_pv

        if not reference:
            reference = f"N°/{year_two_digits}/{num_acte}"

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

  <p style="text-align:center;font-size:17pt;font-weight:bold;text-decoration:underline;
            margin:1pt 0 1pt 0;">
    {title}
  </p>
  <p style="text-align:center;font-size:13pt;font-weight:bold;margin:0 0 8pt 0;">
    {escape(header_number)}
  </p>

  <p style="line-height:1.35;margin-bottom:6pt;font-size:10.8pt;font-weight:bold;">
    Je, soussigné, le Directeur de l'Agence de Contrôle de la Sécurité Sanitaire et de la
    Qualité des Denrées Alimentaires (ACSSQDA), certifie que
  </p>

  <table width="100%" cellspacing="0" cellpadding="2" border="0" style="font-size:10.8pt;line-height:1.2;">
    <tr><td width="24%"><b>Echantillon</b></td><td width="2%">:</td><td><b>{desig}</b></td></tr>
    <tr><td><b>Classe</b></td><td>:</td><td><b>{classe}</b></td></tr>
    <tr><td><b>Quantité</b></td><td>:</td><td><b>{quantite}</b>  <span style="display:inline-block;width:24pt;"></span>
      <b>Quantité Analysée</b> : <b>{quantite_analysee}</b></td></tr>
    <tr><td><b>Date de production</b></td><td>:</td><td><b>{date_production}</b></td></tr>
    <tr><td><b>Date de péremption</b></td><td>:</td><td><b>{date_peremption}</b></td></tr>
    <tr><td><b>Lot</b></td><td>:</td><td><b>{num_lot}</b></td></tr>
    <tr><td><b>Procès-verbal de prélèvement</b></td><td>:</td><td><b>{proces_verbal}</b></td></tr>
    <tr><td><b>Société / Etablissement</b></td><td>:</td><td><b>{fd['company_name']}</b></td></tr>
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
            from reportlab.lib.units import mm
            from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
            from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image
            from reportlab.lib import colors
            fd = self._extract_form_data(form)
            entry = assignments[0]
            pid, product_name, cert_type = entry[0], entry[1], entry[2]
            extras = entry[3] if len(entry) > 3 else {}
            file_path = output_path
            doc = SimpleDocTemplate(
                file_path,
                pagesize=A4,
                rightMargin=16*mm,
                leftMargin=16*mm,
                topMargin=15*mm,
                bottomMargin=15*mm
            )
            story = []
            styles = getSampleStyleSheet()
            # Logos (plus grands)
            logos = self._resolve_logo_sources()
            logo_row = []

            logo_height = 70   # hauteur max
            logo_max_width = 90  # largeur max

            def get_logo(path_key):
                path = logos.get(path_key, "")
                path = self._uri_to_local_path(path)

                if path and Path(path).exists():
                    img = Image(path)
                    ratio = img.imageWidth / img.imageHeight

                    img.drawHeight = logo_height
                    img.drawWidth = logo_height * ratio

                    if img.drawWidth > logo_max_width:
                        img.drawWidth = logo_max_width
                        img.drawHeight = logo_max_width / ratio

                    return img
                return Spacer(1, logo_height)

            # Logos
            left_logo = get_logo("left")
            center_logo = get_logo("center")
            right_logo = get_logo("right")

            # 🔥 Bloc texte centré SOUS le logo du milieu
            center_content = [
                center_logo,
                Spacer(1, 5),
                Paragraph('<para align="center"><b>MINISTÈRE DE LA SANTÉ PUBLIQUE</b></para>', styles['Normal']),
                Paragraph('<para align="center">--------------</para>', styles['Normal']),
                Paragraph('<para align="center"><b>SECRÉTARIAT GÉNÉRAL</b></para>', styles['Normal']),
                Paragraph('<para align="center">--------------</para>', styles['Normal']),
                Spacer(1, 2),
                Paragraph('<para align="center"><b>AGENCE DE CONTRÔLE DE LA SÉCURITÉ SANITAIRE<br/>ET DE LA QUALITÉ DES DENRÉES ALIMENTAIRES</b></para>', styles['Normal']),
                Spacer(1, 2),
            ]

           
            # Tableau principal (3 colonnes)
            table = Table(
                [
                  [left_logo, center_content, right_logo],
                  [],
                  [],
                  []
                ],
                colWidths=[doc.width/2.8]*3
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

            story.append(table)
            story.append(Spacer(1, 10))
            year_two_digits = date.today().strftime("%y")
            header_number = f"N°/{year_two_digits}MSANP/SG/ACSSQDA/{cert_type}"
            if extras.get("num_cert", ""):
              header_number = f"N°{extras.get('num_cert')}/{year_two_digits}MSANP/SG/ACSSQDA/{cert_type}"

            proces_verbal = extras.get("proces_verbal", "")
            if not proces_verbal:
              num_prelevement = str(extras.get("num_prelevement", "") or "").strip()
              date_pv = str(extras.get("date_pv", "") or "").strip()
              if num_prelevement and date_pv:
                proces_verbal = f"N°{num_prelevement}/{year_two_digits}/MIC/SG/DGC/DPC/PRL du {date_pv}"
              elif num_prelevement:
                proces_verbal = f"N°{num_prelevement}/{year_two_digits}/MIC/SG/DGC/DPC/PRL"
              elif date_pv:
                proces_verbal = date_pv

            title_table = Table(
                [
                  [
                    Paragraph('<para align="center"><font size=16><b><u>%s</u></b></font></para>' % _TITLES[cert_type], styles['Normal']),
                  ],
                  [
                    Paragraph(f'<para align="center"><b>{header_number}</b></para>', styles['Normal']),
                  ],
                  [],
                  [],
                  []
                ],
                colWidths=[doc.width]
            )
            title_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ]))

            story.append(title_table)
            story.append(Paragraph("Je, soussigné, le Directeur de l'Agence de Contrôle de la Sécurité Sanitaire et de la Qualité des Denrées Alimentaires (ACSSQDA), certifie que", ParagraphStyle('main', fontSize=11, leading=14, spaceAfter=8)))
            
            # Tableau infos produit (sans bordure)
            data = [
                ["Echantillon", product_name, '', ''],
                ["Classe", extras.get("classe", ""), '', ''],
                ["Quantité", extras.get("quantite", ""), "Quantité Analysée", extras.get("quantite_analysee", "")],
                ["Date de production", extras.get("date_production", ""), '', ''],
                ["Date de péremption", extras.get("date_peremption", ""), '', ''],
                ["Lot", extras.get("num_lot", ""), '', ''],
                ["Procès-verbal de prélèvement", extras.get("proces_verbal", ""), '', ''],
                ["Société / Etablissement", fd['company_name'], '', ''],
                ["Analyse", extras.get("analyse", ""), '', ''],
                ["Référence", extras.get("reference", f"N°/{year_two_digits}/{extras.get('num_acte','')}") , '', ''],
            ]
            table = Table(data, colWidths=[110, 120, 110, 120])
            table.setStyle(TableStyle([
                ('SPAN', (0,2), (1,2)),
                ('SPAN', (2,2), (3,2)),
                ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
                ('FONTSIZE', (0,0), (-1,-1), 10),
                ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                # Pas de bordure !
                ('LINEBELOW', (0,0), (-1,-1), 0, colors.white),
                ('LINEABOVE', (0,0), (-1,-1), 0, colors.white),
                ('LINEBEFORE', (0,0), (-1,-1), 0, colors.white),
                ('LINEAFTER', (0,0), (-1,-1), 0, colors.white),
                ('LEFTPADDING', (0,0), (-1,-1), 2),
                ('RIGHTPADDING', (0,0), (-1,-1), 2),
                ('TOPPADDING', (0,0), (-1,-1), 2),
                ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ]))
            story.append(table)
            story.append(Spacer(1, 10))
            # Résultat
            result_text = "consommable" if cert_type == "CC" else "non consommable"
            story.append(Paragraph(f"<b>Est déclaré {result_text} à la consommation humaine</b>", ParagraphStyle('res', fontSize=11, leading=14, spaceAfter=8)))
            story.append(Paragraph("En foi de quoi, ce certificat est délivré pour servir et valoir ce que de droit.", ParagraphStyle('main2', fontSize=10, leading=13, spaceAfter=8)))
            # Signature
            story.append(Paragraph(f"<para align='right'>Fait à Antananarivo, le {fd['date']}</para>", styles['Normal']))
            story.append(Spacer(1, 8))
            story.append(Paragraph("<para align='right'><b>Le Directeur,</b></para>", styles['Normal']))
            story.append(Spacer(1, 36))
            # Note de bas de page
            story.append(Paragraph("<i>*Ce certificat est valable uniquement pour le LOT ayant fait l'objet d'analyse mentionnée ci-dessus</i>", ParagraphStyle('footer', fontSize=9, leading=11)))
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
