# -*- coding: utf-8 -*-
from odoo import fields, models


class SobtoParcours(models.Model):
    _name = 'sobto.parcours'
    _description = 'Parcours transport (liste)'
    _order = 'name'

    name = fields.Char(string='Libellé', required=True, translate=False)
