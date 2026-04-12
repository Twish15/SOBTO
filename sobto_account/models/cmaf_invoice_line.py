# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Immatriculations autorisées sur les lignes facture CIMAF (cf. data/cmaf_camions.xml)
CIMAF_CAMION_NAMES = ('999WW1426', '999WW1455', '999WW1151')


class CmafInvoiceLine(models.Model):
    _name = 'cmaf.invoice.line'
    _description = 'Ligne facture CIMAF'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    display_type = fields.Selection(
        [
            ('product', 'Ligne'),
            ('line_section', 'Section'),
        ],
        string='Type de ligne',
        default='product',
        required=True,
    )
    name = fields.Char(
        string='Intitulé section',
        help='Texte affiché sur le PDF pour une ligne de type Section.',
    )
    move_id = fields.Many2one(
        'account.move',
        string='Facture',
        required=True,
        ondelete='cascade',
        index=True,
    )
    num_ordre = fields.Integer(string="N° d'ordre", default=1, copy=False)
    camion_id = fields.Many2one(
        'sobto.camion',
        string='Camion',
        ondelete='set null',
        domain=[('name', 'in', list(CIMAF_CAMION_NAMES))],
    )
    product_type = fields.Selection(
        [
            ('tuff', 'TUFF'),
            ('gasoil', 'Gasoil'),
            ('super', 'Super'),
            ('petrole', 'Pétrole'),
        ],
        string='Produit',
        default='tuff',
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
    prix_tonne = fields.Float(
        string='Prix à la tonne',
        digits=(16, 3),
        default=3500.0,
    )
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

    @api.constrains('camion_id', 'display_type')
    def _check_cmaf_camion_required(self):
        for line in self:
            if line.display_type == 'product' and not line.camion_id:
                raise UserError(_('Le camion est obligatoire sur chaque ligne CIMAF.'))

    @api.depends('poids_1ere', 'poids_2eme', 'display_type')
    def _compute_weights(self):
        for line in self:
            if line.display_type == 'line_section':
                line.poids_net = 0.0
                line.poids_net_tonne = 0.0
                continue
            pn = (line.poids_1ere or 0.0) - (line.poids_2eme or 0.0)
            line.poids_net = pn
            line.poids_net_tonne = pn / 1000.0 if pn else 0.0

    @api.depends('poids_net_tonne', 'prix_tonne', 'display_type')
    def _compute_amounts(self):
        for line in self:
            if line.display_type == 'line_section':
                line.montant_htva = 0.0
                line.retenue_5 = 0.0
                line.total_net = 0.0
                continue
            htva = (line.poids_net_tonne or 0.0) * (line.prix_tonne or 0.0)
            line.montant_htva = htva
            line.retenue_5 = htva * 0.05
            line.total_net = htva - line.retenue_5

    def _get_product_for_sync(self):
        self.ensure_one()
        if not self.product_type:
            raise UserError(
                _('Sélectionnez un produit (TUFF, Gasoil, Super ou Pétrole) sur chaque ligne CIMAF.')
            )
        xml_id = {
            'tuff': 'sobto_account.product_transport_tuff',
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

    def _assign_num_ordre_on_create(self, vals_list):
        """Numérotation 1, 2, 3… par facture (lignes produit uniquement)."""
        by_move = defaultdict(list)
        for i, vals in enumerate(vals_list):
            if vals.get('display_type', 'product') == 'line_section':
                vals_list[i]['num_ordre'] = 0
                continue
            mid = vals.get('move_id')
            if isinstance(mid, (list, tuple)):
                mid = mid[0] if mid else None
            if mid:
                by_move[mid].append(i)
        for move_id, indices in by_move.items():
            existing = self.search(
                [('move_id', '=', move_id), ('display_type', '=', 'product')]
            ).mapped('num_ordre')
            max_ord = max(existing) if existing else 0
            for idx in indices:
                max_ord += 1
                vals_list[idx]['num_ordre'] = max_ord

    @api.model_create_multi
    def create(self, vals_list):
        self._assign_num_ordre_on_create(vals_list)
        lines = super().create(vals_list)
        lines._after_cmaf_change()
        return lines

    def _renumber_cmaf_product_orders(self):
        for move in self.mapped('move_id'):
            products = move.cmaf_line_ids.filtered(
                lambda l: l.display_type == 'product'
            ).sorted(lambda l: (l.sequence, l.id))
            for i, line in enumerate(products, start=1):
                if line.num_ordre != i:
                    line.with_context(skip_cmaf_after=True).write({'num_ordre': i})

    def write(self, vals):
        if self.env.context.get('skip_cmaf_after'):
            return super().write(vals)
        vals_to_write = dict(vals)
        if vals_to_write.get('display_type') == 'line_section':
            vals_to_write['num_ordre'] = 0
        res = super().write(vals_to_write)
        if 'display_type' in vals_to_write:
            self._renumber_cmaf_product_orders()
        self._after_cmaf_change()
        return res

    def unlink(self):
        moves = self.mapped('move_id')
        res = super().unlink()
        Line = self.env['cmaf.invoice.line']
        for move in moves:
            if move.x_invoice_type == 'cmaf' and move.state == 'draft':
                Line.search([('move_id', '=', move.id)])._renumber_cmaf_product_orders()
                move._sync_invoice_lines_from_cmaf()
        return res

    def _after_cmaf_change(self):
        for move in self.mapped('move_id'):
            if move.x_invoice_type == 'cmaf' and move.state == 'draft':
                move._sync_invoice_lines_from_cmaf()
