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
    x_numero_camion = fields.Char(string='N° Camion', help='Immatriculation du camion')
    x_parcours = fields.Char(string='Parcours', help='Itinéraire du transport')

    @api.depends('price_subtotal')
    def _compute_x_montant_ligne(self):
        for line in self:
            if line.display_type in ('line_section', 'line_note'):
                line.x_montant_ligne = False
            else:
                line.x_montant_ligne = line.price_subtotal

    def _inverse_x_montant_ligne(self):
        for line in self:
            if line.display_type in ('line_section', 'line_note'):
                continue
            qty = line.quantity or 0.0
            factor = 1.0 - (line.discount or 0.0) / 100.0
            if not qty or not factor:
                continue
            line.price_unit = line.x_montant_ligne / (qty * factor)

    @api.model
    def _default_uom_litres(self):
        Uom = self.env['uom.uom']
        uom = Uom.search([('name', 'ilike', 'litre')], limit=1)
        if not uom:
            uom = Uom.search([('name', 'in', ('L', 'l'))], limit=1)
        return uom

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
            if 'quantity' in fields_list:
                qty = res.get('quantity')
                if qty in (False, None) or qty == 0:
                    res['quantity'] = DEFAULT_QTY_LITRES
            if 'product_uom_id' in fields_list and not res.get('product_uom_id'):
                uom = self._default_uom_litres()
                if uom:
                    res['product_uom_id'] = uom.id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            move_id = vals.get('move_id')
            if not move_id:
                continue
            move = self.env['account.move'].browse(move_id)
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue
            if not vals.get('quantity'):
                vals['quantity'] = DEFAULT_QTY_LITRES
            if not vals.get('product_uom_id'):
                uom = self._default_uom_litres()
                if uom:
                    vals['product_uom_id'] = uom.id
        return super().create(vals_list)
