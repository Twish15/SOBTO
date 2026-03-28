# -*- coding: utf-8 -*-
from odoo import fields, models


class SobtoCamion(models.Model):
    _name = 'sobto.camion'
    _description = 'Camion (immatriculation / repère)'
    _order = 'name'

    name = fields.Char(string='Immatriculation / repère', required=True)
