# -*- coding: utf-8 -*-
from odoo import models


class ReportInvoiceSobto(models.AbstractModel):
    """Modèle de rapport pour le template Facture SOBTO (réutilise les valeurs du rapport standard)."""
    _name = 'report.sobto_account.report_invoice_sobto'
    _description = 'Rapport Facture SOBTO'
    _inherit = 'report.account.report_invoice'
