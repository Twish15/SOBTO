# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class TransportInvoiceLine(models.Model):
    _name = 'transport.invoice.line'
    _description = 'Ligne facture transport'
    _order = 'id'

    move_id = fields.Many2one(
        'account.move',
        string='Facture',
        required=True,
        ondelete='cascade',
        index=True,
    )
    date_bl = fields.Date(string='Date B.L')
    bl_number = fields.Char(string='N° B.L')
    date_be = fields.Date(string='Date B.E')
    be_number = fields.Char(string='N° B.E')
    camion_id = fields.Many2one('sobto.camion', string='Camion', ondelete='set null')
    quantity = fields.Float(
        string='Quantité (L)',
        default=45000.0,
        digits=(16, 3),
    )
    product_type = fields.Selection(
        [
            ('gasoil', 'Gasoil'),
            ('super', 'Super'),
            ('petrole', 'Pétrole'),
        ],
        string='Produit',
    )
    parcours_id = fields.Many2one('sobto.parcours', string='Parcours', ondelete='set null')
    taux = fields.Float(string='Taux', digits=(16, 3))
    montant = fields.Monetary(
        string='Montant',
        compute='_compute_montant',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='move_id.currency_id',
        store=True,
        readonly=True,
    )

    @api.depends('taux', 'quantity')
    def _compute_montant(self):
        for line in self:
            line.montant = (line.taux or 0.0) * (line.quantity or 0.0)

    def _get_product_for_sync(self):
        self.ensure_one()
        if not self.product_type:
            raise UserError(_('Sélectionnez un type de produit (Gasoil, Super ou Pétrole) sur chaque ligne transport.'))
        xml_id = {
            'gasoil': 'sobto_account.product_transport_gasoil',
            'super': 'sobto_account.product_transport_super',
            'petrole': 'sobto_account.product_transport_petrole',
        }.get(self.product_type)
        if not xml_id:
            raise UserError(_('Type de produit inconnu.'))
        try:
            return self.env.ref(xml_id)
        except ValueError as e:
            raise UserError(_('Produit de transport manquant (données module).')) from e

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._after_transport_change()
        return lines

    def write(self, vals):
        res = super().write(vals)
        self._after_transport_change()
        return res

    def unlink(self):
        moves = self.mapped('move_id')
        res = super().unlink()
        for move in moves:
            if move.x_invoice_type == 'transport' and move.state == 'draft':
                move._sync_invoice_lines_from_transport()
        return res

    def _after_transport_change(self):
        for move in self.mapped('move_id'):
            if move.x_invoice_type == 'transport' and move.state == 'draft':
                move._sync_invoice_lines_from_transport()
