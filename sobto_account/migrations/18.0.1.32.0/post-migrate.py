# -*- coding: utf-8 -*-
"""Remplit x_camion_id depuis l'ancien champ texte x_numero_camion (lignes Transit)."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    Camion = env['sobto.camion']
    Line = env['account.move.line']
    lines = Line.search(
        [('x_numero_camion', '!=', False), ('x_camion_id', '=', False)]
    )
    for line in lines:
        name = (line.x_numero_camion or '').strip()
        if not name:
            continue
        cam = Camion.search([('name', '=', name)], limit=1)
        if not cam:
            cam = Camion.create({'name': name})
        line.write({'x_camion_id': cam.id})
