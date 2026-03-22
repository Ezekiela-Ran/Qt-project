from pathlib import Path
from html import escape

from PySide6 import QtWidgets
from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
from PySide6.QtWidgets import QMessageBox
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog, QPrintDialog

from utils.text_utils import TextUtils


class InvoicePrinter:
    def __init__(self, parent_widget):
        self.parent = parent_widget

    def _resolve_logo_src(self):
        logo_path = Path(__file__).resolve().parent.parent / "images" / "image.png"
        return logo_path.as_uri() if logo_path.exists() else ""

    def _load_print_css(self):
        try:
            with open("styles/invoice_print.css", "r", encoding="utf-8") as css_file:
                return css_file.read()
        except FileNotFoundError:
            return ""

    def generate_invoice_html(self, form, invoice_type, selected_products, db_manager, ref_mapping=None):
        company_name    = form.company_name_input.text().strip()
        responsable     = form.responsable_input.text().strip()
        stat            = form.stat_input.text().strip()
        nif             = form.nif_input.text().strip()
        address         = form.address_input.text().strip() if hasattr(form, 'address_input') else ""

        if invoice_type == 'standard':
            date_issue      = form.date_issue_input.date().toString('dd/MM/yyyy') if hasattr(form, 'date_issue_input') else ''
            date_result     = form.date_result_input.date().toString('dd/MM/yyyy') if hasattr(form, 'date_result_input') else ''
            product_ref_raw = form.product_ref_input.text() if hasattr(form, 'product_ref_input') else ''
            title           = 'FACTURE'
        else:
            date_issue      = form.date_input.date().toString('dd/MM/yyyy') if hasattr(form, 'date_input') else ''
            date_result     = ''
            product_ref_raw = ''
            title           = 'FACTURE PROFORMA'

        products = []
        for pid in selected_products:
          prod = db_manager.get_product_by_id(pid)
          if not prod:
            continue
          # prefer ref from ref_mapping (in-memory dynamic numbering) if provided
          if ref_mapping and pid in ref_mapping:
            prod = dict(prod)  # shallow copy
            prod['ref_b_analyse'] = ref_mapping.get(pid)
          products.append(prod)
        total           = sum(float(p.get('subtotal', 0) or 0) for p in products)
        total_formatted = f"{total:,.0f}".replace(',', '\u00a0')
        total_words     = TextUtils.number_to_words(round(total)).upper()

        company_name = escape(company_name)
        responsable  = escape(responsable)
        stat         = escape(stat)
        nif          = escape(nif)
        address      = escape(address)
        issue_label  = escape(date_issue)
        result_label = escape(date_result)
        product_ref  = escape(product_ref_raw)

        logo_src = self._resolve_logo_src()
        logo_tag = (f'<img src="{logo_src}" width="90" height="75" style="object-fit:contain;">'
                    if logo_src else '<span style="display:inline-block;width:90px;height:75px;"></span>')

        # ---- ENTÊTE: tableau HTML 2 colonnes (agency | DOIT box) ----
        header = f"""
<table width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;margin:0 0 4pt 0;">
  <tr>
    <td width="68%" valign="middle" style="padding-right:8pt;">
      <table cellspacing="0" cellpadding="0" border="0" width="100%">
        <tr>
          <td width="90" valign="top" style="text-align:center;padding-right:8pt;padding-bottom:4pt;">{logo_tag}</td>
          <td valign="middle" style="border-top:1.5px solid #000;border-bottom:1.5px solid #000;
              padding:6pt 8pt;font-size:11pt;font-weight:bold;
              text-transform:uppercase;line-height:1.4;vertical-align:middle;">
            AGENCE DE CONTRÔLE DE<br>
            LA SECURITE SANITAIRE<br>
            ET DE LA QUALITE DES<br>
            DENREES ALIMENTAIRES
          </td>
        </tr>
      </table>
      <table cellspacing="0" cellpadding="3" border="0" style="margin-top:6pt;width:100%;">
        <tr>
          <td style="width:50pt;font-style:italic;font-size:9pt;font-weight:bold;">NIF:</td>
          <td style="font-style:italic;font-size:9pt;">2001451249</td>
        </tr>
        <tr>
          <td style="font-style:italic;font-size:9pt;font-weight:bold;">STAT:</td>
          <td style="font-style:italic;font-size:9pt;">86,909,112,006,001,800</td>
        </tr>
        <tr>
          <td style="font-style:italic;font-size:9pt;font-weight:bold;">TEL:</td>
          <td style="font-style:italic;font-size:9pt;">22 222 39</td>
        </tr>
        <tr>
          <td style="font-style:italic;font-size:9pt;font-weight:bold;">Adresse:</td>
          <td style="font-style:italic;font-size:9pt;">Rue Karidja Tsaralalàna<br>(Ex Bâtiment Pharmacie Centrale Face Hôtel de Police)</td>
        </tr>
      </table>
    </td>
    <td width="32%" valign="top" style="border:1.5px solid #000;padding:0;min-height:200px;">
      <table width="100%" cellspacing="0" cellpadding="0" border="0" style="height:100%;">
        <tr>
          <td align="center" style="font-size:14pt;font-weight:bold;padding:6pt 0;border-bottom:1px solid #000;">DOIT</td>
        </tr>
        <tr style="height:100%;">
          <td style="padding:8pt;vertical-align:bottom;">
            <p style="font-style:italic;font-size:9pt;margin:0 0 6pt 0;"><strong>Raison social:</strong> {company_name}</p>
            <p style="font-style:italic;font-size:9pt;margin:0 0 6pt 0;"><strong>Statistique:</strong> {stat}</p>
            <p style="font-style:italic;font-size:9pt;margin:0 0 6pt 0;"><strong>NIF:</strong> {nif}</p>
            <p style="font-style:italic;font-size:9pt;margin:0;"><strong>Adresse:</strong> {address}</p>
          </td>
        </tr>
      </table>
    </td>
  </tr>
</table>
<h2 style="text-align:center;font-style:italic;font-weight:bold;font-size:18pt;margin:4pt 0;">{title}</h2>
"""

        # ---- Création des lignes de produits ----
        rows = ''
        for prod in products:
            ref_b    = escape(str(prod.get('ref_b_analyse', '') or ''))
            desig    = escape(str(prod.get('product_name',  '') or ''))
            num_act  = escape(str(prod.get('num_act',       '') or ''))
            physico  = escape(str(prod.get('physico',       '') or ''))
            micro    = escape(str(prod.get('micro',         '') or ''))
            toxico   = escape(str(prod.get('toxico',        '') or ''))
            subtotal = escape(str(prod.get('subtotal',      '') or ''))
            rows += (f'<tr style="font-size:11pt;line-height:1.6;"><td style="border:1px solid #000;padding:8pt 8pt;">{ref_b}</td><td style="border:1px solid #000;padding:8pt 8pt;">{desig}</td><td style="border:1px solid #000;padding:8pt 8pt;">{num_act}</td>'
                     f'<td style="text-align:right;border:1px solid #000;padding:8pt 8pt;">{physico}</td>'
                     f'<td style="text-align:right;border:1px solid #000;padding:8pt 8pt;">{micro}</td>'
                     f'<td style="text-align:right;border:1px solid #000;padding:8pt 8pt;">{toxico}</td>'
                     f'<td style="text-align:right;border:1px solid #000;padding:8pt 8pt;">{subtotal}</td></tr>')

        # ---- SECTION MÉTADONNÉES au-dessus du tableau ----
        metadata = f"""
<table width="100%" cellspacing="0" cellpadding="0" border="0" style="width:100%;margin:0 0 4pt 0;">
  <tr>
    <td width="25%" style="padding:4pt 8pt;font-style:italic;font-size:9pt;"><strong>Date d'émission:</strong> {issue_label}</td>
    <td width="25%" style="padding:4pt 8pt;font-style:italic;font-size:9pt;"><strong>Référence(s) produits:</strong> {product_ref}</td>
    <td width="25%" style="padding:4pt 8pt;font-style:italic;font-size:9pt;"><strong>Date du résultat:</strong> {result_label}</td>
    <td width="25%" style="padding:4pt 8pt;font-style:italic;font-size:9pt;"><strong>Responsable:</strong> {responsable}</td>
  </tr>
</table>
"""

        table = f"""
<table class="invoice-table" cellspacing="0" cellpadding="0" style="width:100%;margin:0;">
  <thead>
    <tr style="background-color:#e8e8e8;">
      <th style="width:12%;font-weight:bold;font-style:italic;font-size:10pt;border:1px solid #000;padding:8pt 8pt;min-height:32pt;">Réf.<br>Bulletin<br>d'analyse</th>
      <th style="width:22%;font-weight:bold;font-style:italic;font-size:10pt;border:1px solid #000;padding:8pt 8pt;min-height:32pt;">Désignations</th>
      <th style="width:14%;font-weight:bold;font-style:italic;font-size:10pt;border:1px solid #000;padding:8pt 8pt;min-height:32pt;">N°Acte de<br>prélèvement</th>
      <th style="width:12%;font-weight:bold;font-style:italic;font-size:10pt;border:1px solid #000;padding:8pt 8pt;min-height:32pt;">Physico<br>chimique</th>
      <th style="width:12%;font-weight:bold;font-style:italic;font-size:10pt;border:1px solid #000;padding:8pt 8pt;min-height:32pt;">Micro-<br>biologique</th>
      <th style="width:12%;font-weight:bold;font-style:italic;font-size:10pt;border:1px solid #000;padding:8pt 8pt;min-height:32pt;">Toxico-<br>logique</th>
      <th style="width:16%;font-weight:bold;font-style:italic;font-size:10pt;border:1px solid #000;padding:8pt 8pt;min-height:32pt;">Sous-total</th>
    </tr>
  </thead>
  <tbody>
{rows}
  </tbody>
  <tfoot>
    <tr style="font-style:italic;font-size:11pt;font-weight:bold;">
      <td style="text-align:right;padding:8pt;border:1px solid #000;border-top:1.5px solid #000;" colspan="5">Montant à payer</td>
      <td style="text-align:right;padding:8pt;border:1px solid #000;border-top:1.5px solid #000;" colspan="2">{total_formatted} Ar</td>
    </tr>
  </tfoot>
</table>
"""

        # ---- PIED DE PAGE ----
        footer = f"""
<div class="invoice-footer">
  <p style="margin:12pt 0 6pt;font-weight:bold;font-style:italic;font-size:10pt;">Arrêtée la présente facture à la somme de&nbsp;: {escape(total_words)} ARIARY</p>
  <p style="margin:6pt 0;font-style:italic;font-size:10pt;">Mode de paiement
    <span style="margin-left:30pt;">☐ Espèces</span>
    <span style="margin-left:44pt;">☐ Chèque</span>
  </p>
  <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:28pt;">
    <tr>
      <td width="50%" style="text-align:center;font-size:9pt;border-top:1.5px solid #000;padding-top:6pt;">Le Client</td>
      <td width="50%" style="text-align:center;font-size:9pt;border-top:1.5px solid #000;padding-top:6pt;">Le(a) Caissier(e)</td>
    </tr>
  </table>
  <table width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:22pt;">
    <tr>
      <td style="font-size:8pt;">(*) Chèque visé à l'ordre de Madame le RECEVEUR GENERAL .</td>
      <td align="right" style="font-size:8pt;">Quittance N°______________</td>
    </tr>
  </table>
</div>
"""

        css = self._load_print_css()
        return f"""<!DOCTYPE HTML>
<html>
<head>
  <meta charset="UTF-8">
  <style>{css}</style>
</head>
<body>
<div class="invoice-root">
{header}
{metadata}
{table}
{footer}
</div>
</body>
</html>"""


    def preview_invoice(self, html):
        if not html:
            QMessageBox.warning(self.parent, 'Aperçu impossible', 'Impossible de générer l’aperçu. Vérifiez les données.')
            return

        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageLayout(
            QPageLayout(
                QPageSize(QPageSize.A4),
                QPageLayout.Portrait,
                QMarginsF(6, 6, 6, 6)
            )
        )

        def render_preview(p):
            doc = QTextDocument()
            doc.setDocumentMargin(0)
            doc.setHtml(html)
            doc.setPageSize(p.pageRect(QPrinter.Point).size())
            doc.print_(p)

        preview = QPrintPreviewDialog(printer, self.parent)
        preview.setWindowTitle('Aperçu de la facture')
        preview.paintRequested.connect(render_preview)
        preview.exec()

    def print_invoice(self, html):
        if not html:
            QMessageBox.warning(self.parent, 'Impression impossible', 'Impossible de générer l’impression. Vérifiez les données.')
            return

        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageLayout(
            QPageLayout(
                QPageSize(QPageSize.A4),
                QPageLayout.Portrait,
            QMarginsF(6, 6, 6, 6)
            )
        )

        dialog = QPrintDialog(printer, self.parent)
        if dialog.exec() == QtWidgets.QDialog.Accepted:
            doc = QTextDocument()
            doc.setDocumentMargin(0)
            doc.setHtml(html)
            doc.setPageSize(printer.pageRect(QPrinter.Point).size())
            doc.print_(printer)