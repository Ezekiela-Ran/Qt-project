"""
Génération HTML et impression des certificats CC / CNC.

Chaque certificat occupe une page A4 portrait.
L'impression utilise QPrinter / QPrintDialog (même approche que InvoicePrinter).
"""
from datetime import date
from pathlib import Path
from html import escape

from PySide6.QtGui import QTextDocument, QPageSize, QPageLayout
from PySide6.QtCore import QMarginsF
from PySide6.QtPrintSupport import QPrinter, QPrintDialog


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
        proces_verbal     = escape(extras.get("proces_verbal", ""))
        reference         = escape(extras.get("reference", ""))

        analyse_sentence = self._build_analysis_sentence(analyse_raw)
        result_text = "consommable" if cert_type == "CC" else "non consommable"
        year_two_digits = date.today().strftime("%y")
        header_number = f"N°/{year_two_digits}MSANP/SG/ACSSQDA/{cert_type}"

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

    # ------------------------------------------------------------------
    # Impression
    # ------------------------------------------------------------------

    def print_certificates(self, form, assignments: list[tuple]):
        """Affiche le dialogue d'impression et imprime tous les certificats."""
        html = self.generate_html(form, assignments)

        printer = QPrinter(QPrinter.HighResolution)
        printer.setPageSize(QPageSize(QPageSize.A4))
        printer.setPageOrientation(QPageLayout.Portrait)
        printer.setPageMargins(QMarginsF(6, 6, 6, 6), QPageLayout.Millimeter)

        dlg = QPrintDialog(printer, self.parent)
        if dlg.exec() != QPrintDialog.Accepted:
            return

        doc = QTextDocument()
        doc.setHtml(html)
        doc.print_(printer)
