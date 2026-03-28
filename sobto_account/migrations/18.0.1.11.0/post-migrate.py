# -*- coding: utf-8 -*-
"""Parcours : copie texte → liste. TVA vente par défaut 15 % → 18 %."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})

    for company in env['res.company'].search([]):
        tax = getattr(company, 'account_sale_tax_id', None)
        if (
            tax
            and tax.amount_type == 'percent'
            and abs(tax.amount - 15.0) < 0.0001
        ):
            tax.sudo().write({'amount': 18.0})

    Line = env['account.move.line'].sudo()
    Parcours = env['sobto.parcours'].sudo()
    lines = Line.search([('x_parcours', '!=', False), ('x_parcours_id', '=', False)])
    for line in lines:
        name = (line.x_parcours or '').strip()
        if not name:
            continue
        p = Parcours.search([('name', '=', name)], limit=1)
        if not p:
            p = Parcours.create({'name': name})
        line.x_parcours_id = p
