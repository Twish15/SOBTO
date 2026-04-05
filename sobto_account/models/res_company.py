# -*- coding: utf-8 -*-
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    x_invoice_signature = fields.Image(
        string='Signature (facture PDF)',
        help='Image de la signature affichée sur le PDF facture SOBTO, sous le nom du signataire.',
        max_width=1920,
        max_height=1920,
    )
    x_invoice_stamp = fields.Image(
        string='Tampon (facture PDF)',
        help='Image du tampon affichée sur le PDF facture SOBTO.',
        max_width=1920,
        max_height=1920,
    )
    x_cmaf_payment_rib = fields.Text(
        string='Compte / libellé paiement CIMAF (PDF)',
        default=(
            "N° 171 01601 060494104001 - 41 ORABANK INTITULE CODEC OUAGA N°103/02212"
        ),
        help='Texte affiché après « SUR LE COMPTE : » sur la facture CIMAF.',
    )
