from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    x_date_bl = fields.Date(string='Date B.L', help='Date du Bon de Livraison')
    x_numero_bl = fields.Char(string='N° B.L', help='Numéro du Bon de Livraison')
    x_date_be = fields.Date(string='Date B.E', help="Date du Bon d'Enlèvement")
    x_numero_be = fields.Char(string='N° B.E', help="Numéro du Bon d'Enlèvement")
    x_numero_camion = fields.Char(string='N° Camion', help='Immatriculation du camion')
    x_parcours = fields.Char(string='Parcours', help='Itinéraire du transport')
