# -*- coding: utf-8 -*-
"""Produits transport : UdM Unités → Litres (cohérence avec quantités en L)."""


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    litre = env.ref('uom.product_uom_litre', raise_if_not_found=False)
    if not litre:
        return
    for xmlid in (
        'sobto_account.product_transport_gasoil',
        'sobto_account.product_transport_super',
        'sobto_account.product_transport_petrole',
    ):
        try:
            prod = env.ref(xmlid)
        except ValueError:
            continue
        tmpl = prod.product_tmpl_id
        tmpl.write({'uom_id': litre.id, 'uom_po_id': litre.id})
