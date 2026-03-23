from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_rccm = fields.Char(string='N° RCCM', help='Numéro du Registre du Commerce et du Crédit Mobilier')
    x_ifu = fields.Char(string='N° IFU', help='Numéro Identifiant Fiscal Unique')
    x_dge_rni = fields.Char(string='DGE/RNI', help='Direction Générale des Entreprises / Répertoire National des Entreprises')
