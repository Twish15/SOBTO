from collections import defaultdict

from odoo import api, fields, models

DEFAULT_QTY_LITRES = 45000.0


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    x_montant_ligne = fields.Monetary(
        string='Montant',
        compute='_compute_x_montant_ligne',
        inverse='_inverse_x_montant_ligne',
        currency_field='currency_id',
        help='Montant HT de la ligne ; modifiable pour recalculer le prix unitaire.',
    )

    x_date_bl = fields.Date(string='Date B.L', help='Date du Bon de Livraison')
    x_numero_bl = fields.Char(string='N° B.L', help='Numéro du Bon de Livraison')
    x_date_be = fields.Date(string='Date B.E', help="Date du Bon d'Enlèvement")
    x_numero_be = fields.Char(string='N° B.E', help="Numéro du Bon d'Enlèvement")
    x_numero_camion = fields.Char(
        string='N° Camion (ancien)',
        help='Conservé pour migration / affichage ; utiliser le champ Camion.',
    )
    x_camion_id = fields.Many2one(
        'sobto.camion',
        string='Camion',
        ondelete='set null',
        help='Immatriculation ou repère (liste paramétrable, comme CIMAF).',
    )
    x_parcours_id = fields.Many2one(
        'sobto.parcours',
        string='Parcours',
        ondelete='set null',
        help='Itinéraire (liste paramétrable).',
    )
    x_parcours = fields.Char(
        string='Parcours (ancien)',
        help='Conservé pour migration ; utiliser le champ Parcours (liste).',
    )
    x_total_ddu = fields.Monetary(
        string='Total DDU',
        currency_field='currency_id',
        help='Montant DDU saisi pour la ligne Transit.',
    )
    x_rs = fields.Monetary(
        string='RS',
        currency_field='currency_id',
        help='Montant RS saisi pour la ligne Transit.',
    )

    def _get_transit_formula_amount(self):
        self.ensure_one()
        return (self.x_total_ddu or 0.0) - ((self.x_rs or 0.0) + 25000.0)

    def _apply_transit_formula_price(self):
        for line in self:
            move = line.move_id
            if (
                not move
                or move.x_invoice_type != 'transit'
                or line.display_type in ('line_section', 'line_note')
            ):
                continue
            qty = line.quantity or 0.0
            factor = 1.0 - (line.discount or 0.0) / 100.0
            if not qty or not factor:
                continue
            target = line._get_transit_formula_amount()
            line.with_context(skip_transit_formula_sync=True).price_unit = (
                target / (qty * factor)
            )

    @api.depends('price_subtotal', 'x_total_ddu', 'x_rs', 'move_id.x_invoice_type')
    def _compute_x_montant_ligne(self):
        for line in self:
            if line.display_type in ('line_section', 'line_note'):
                line.x_montant_ligne = False
            elif line.move_id.x_invoice_type == 'transit':
                line.x_montant_ligne = line._get_transit_formula_amount()
            else:
                line.x_montant_ligne = line.price_subtotal

    def _inverse_x_montant_ligne(self):
        for line in self:
            if line.display_type in ('line_section', 'line_note'):
                continue
            if line.move_id.x_invoice_type == 'transit':
                line.x_total_ddu = (line.x_montant_ligne or 0.0) + (line.x_rs or 0.0) + 25000.0
                line._apply_transit_formula_price()
                continue
            qty = line.quantity or 0.0
            factor = 1.0 - (line.discount or 0.0) / 100.0
            if not qty or not factor:
                continue
            line.price_unit = line.x_montant_ligne / (qty * factor)

    @api.onchange('x_total_ddu', 'x_rs', 'quantity', 'discount')
    def _onchange_transit_formula_fields(self):
        self._apply_transit_formula_price()

    @api.model
    def _default_uom_litres(self):
        Uom = self.env['uom.uom']
        uom = Uom.search([('name', 'ilike', 'litre')], limit=1)
        if not uom:
            uom = Uom.search([('name', 'in', ('L', 'l'))], limit=1)
        return uom

    def _get_transit_default_camion(self, move, line_index):
        """Alterne les deux camions Transit par défaut (ligne 1, 2, 1, 2…)."""
        if not move or move.x_invoice_type != 'transit':
            return self.env['sobto.camion']
        cam1 = self.env.ref(
            'sobto_account.camion_transit_7895', raise_if_not_found=False
        )
        cam2 = self.env.ref(
            'sobto_account.camion_transit_7812', raise_if_not_found=False
        )
        pick = cam1 if (line_index % 2 == 0) else cam2
        return pick or cam1 or cam2 or self.env['sobto.camion']

    def _assign_transit_camion_defaults(self, vals_list):
        by_move = defaultdict(list)
        for i, vals in enumerate(vals_list):
            mid = vals.get('move_id')
            if isinstance(mid, (list, tuple)):
                mid = mid[0] if mid else None
            if not mid:
                continue
            if vals.get('x_camion_id'):
                continue
            if 'x_camion_id' in vals and not vals.get('x_camion_id'):
                continue
            by_move[mid].append(i)
        for move_id, indices in by_move.items():
            move = self.env['account.move'].browse(move_id)
            if move.x_invoice_type != 'transit':
                continue
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue
            existing = len(
                move.invoice_line_ids.filtered(
                    lambda l: l.display_type == 'product'
                )
            )
            for j, idx in enumerate(indices):
                cam = self._get_transit_default_camion(move, existing + j)
                if cam:
                    vals_list[idx]['x_camion_id'] = cam.id

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        ctx = self.env.context
        move_type = ctx.get('default_move_type')
        move_id = ctx.get('default_move_id') or ctx.get('default_parent_id')
        if move_id and not move_type:
            move = self.env['account.move'].browse(move_id)
            move_type = move.move_type
        if move_type in ('out_invoice', 'out_refund'):
            move = self.env['account.move'].browse(move_id) if move_id else None
            transit_invoice = move and move.x_invoice_type == 'transit'
            if transit_invoice:
                if fields_list is None or 'quantity' in fields_list:
                    qty = res.get('quantity')
                    if qty in (False, None) or qty == 0:
                        res['quantity'] = DEFAULT_QTY_LITRES
                if (fields_list is None or 'product_uom_id' in fields_list) and not res.get(
                    'product_uom_id'
                ):
                    uom = self._default_uom_litres()
                    if uom:
                        res['product_uom_id'] = uom.id
            load_camion = fields_list is None or 'x_camion_id' in fields_list
            if load_camion and move_id and not res.get('x_camion_id'):
                move = self.env['account.move'].browse(move_id)
                if move.x_invoice_type == 'transit':
                    idx = len(
                        move.invoice_line_ids.filtered(
                            lambda l: l.display_type == 'product'
                        )
                    )
                    cam = self._get_transit_default_camion(move, idx)
                    if cam:
                        res['x_camion_id'] = cam.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        self._assign_transit_camion_defaults(vals_list)
        for vals in vals_list:
            move_id = vals.get('move_id')
            if not move_id:
                continue
            move = self.env['account.move'].browse(move_id)
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue
            if move.x_invoice_type == 'transit':
                if not vals.get('quantity'):
                    vals['quantity'] = DEFAULT_QTY_LITRES
                if not vals.get('product_uom_id'):
                    uom = self._default_uom_litres()
                    if uom:
                        vals['product_uom_id'] = uom.id
        lines = super().create(vals_list)
        lines._apply_transit_formula_price()
        for line in lines:
            move = line.move_id
            if (
                move.state == 'draft'
                and move.x_invoice_type in ('transit', 'simple')
                and not move.x_apply_tva
                and line.display_type == 'product'
                and move.move_type in ('out_invoice', 'out_refund')
            ):
                line.write({'tax_ids': [(5, 0, 0)]})
        return lines

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get('skip_transit_formula_sync'):
            return res
        if {'x_total_ddu', 'x_rs', 'quantity', 'discount'} & set(vals):
            self._apply_transit_formula_price()
        return res
