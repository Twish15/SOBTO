# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CmafInvoiceLine(models.Model):
    _name = 'cmaf.invoice.line'
    _description = 'Ligne facture CIMAF'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    move_id = fields.Many2one(
        'account.move',
        string='Facture',
        required=True,
        ondelete='cascade',
        index=True,
    )
    num_ordre = fields.Integer(string="N° d'ordre", default=1)
    camion_id = fields.Many2one('sobto.camion', string='Camion', ondelete='set null')
    product_type = fields.Selection(
        [
            ('gasoil', 'Gasoil'),
            ('super', 'Super'),
            ('petrole', 'Pétrole'),
        ],
        string='Produit',
    )
    ticket_pesee_bf = fields.Char(string='Ticket de pesée BF')
    date_sortie = fields.Date(string='Date de sortie')
    poids_1ere = fields.Float(string='Poids 1ère pesée', digits=(16, 3))
    poids_2eme = fields.Float(string='Poids 2ème pesée', digits=(16, 3))
    poids_net = fields.Float(
        string='Poids Net',
        compute='_compute_weights',
        store=True,
        digits=(16, 3),
    )
    poids_net_tonne = fields.Float(
        string='Poids Net / Tonne',
        compute='_compute_weights',
        store=True,
        digits=(16, 3),
    )
    prix_tonne = fields.Float(string='Prix à la tonne', digits=(16, 3))
    montant_htva = fields.Monetary(
        string='Montant HTVA',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    retenue_5 = fields.Monetary(
        string='Retenue 5 %',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    total_net = fields.Monetary(
        string='Total Net',
        compute='_compute_amounts',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='move_id.currency_id',
        store=True,
        readonly=True,
    )

    @api.depends('poids_1ere', 'poids_2eme')
    def _compute_weights(self):
        for line in self:
            pn = (line.poids_1ere or 0.0) - (line.poids_2eme or 0.0)
            line.poids_net = pn
            line.poids_net_tonne = pn / 1000.0 if pn else 0.0

    @api.depends('poids_net_tonne', 'prix_tonne')
    def _compute_amounts(self):
        for line in self:
            htva = (line.poids_net_tonne or 0.0) * (line.prix_tonne or 0.0)
            line.montant_htva = htva
            line.retenue_5 = htva * 0.05
            line.total_net = htva - line.retenue_5

    def _get_product_for_sync(self):
        self.ensure_one()
        if not self.product_type:
            raise UserError(_('Sélectionnez un produit (Gasoil, Super ou Pétrole) sur chaque ligne CIMAF.'))
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
        lines._after_cmaf_change()
        return lines

    def write(self, vals):
        res = super().write(vals)
        self._after_cmaf_change()
        return res

    def unlink(self):
        moves = self.mapped('move_id')
        res = super().unlink()
        for move in moves:
            if move.x_invoice_type == 'cmaf' and move.state == 'draft':
                move._sync_invoice_lines_from_cmaf()
        return res

    def _after_cmaf_change(self):
        for move in self.mapped('move_id'):
            if move.x_invoice_type == 'cmaf' and move.state == 'draft':
                move._sync_invoice_lines_from_cmaf()
