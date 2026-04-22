import re

from odoo import api, fields, models

try:
    from num2words import num2words
except ImportError:
    num2words = None

MOIS_FR = [
    'janvier', 'fevrier', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'aout', 'septembre', 'octobre', 'novembre', 'decembre'
]


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    x_date_order_fr = fields.Char(
        string='Date devis (FR)',
        compute='_compute_x_date_order_fr',
    )
    x_montant_lettres_devis = fields.Char(
        string='Montant en lettres (devis)',
        compute='_compute_x_montant_lettres_devis',
    )

    @api.depends('date_order')
    def _compute_x_date_order_fr(self):
        for order in self:
            if order.date_order:
                d = fields.Datetime.context_timestamp(order, order.date_order).date()
                order.x_date_order_fr = f"{d.day:02d} {MOIS_FR[d.month - 1]} {d.year}"
            else:
                order.x_date_order_fr = ''

    @api.depends('amount_total', 'currency_id')
    def _compute_x_montant_lettres_devis(self):
        for order in self:
            if not num2words:
                order.x_montant_lettres_devis = ''
                continue
            if not order.amount_total:
                order.x_montant_lettres_devis = ''
                continue
            amount_val = abs(round(order.amount_total))
            amount_str = num2words(amount_val, lang='fr').upper()
            num_in_paren = f"{amount_val:,}".replace(',', ' ')
            order.x_montant_lettres_devis = (
                f"{amount_str} ( {num_in_paren} ) Francs CFA TTC"
            )

    @api.model
    def _next_sobto_quotation_name(self, order_date=None):
        if not order_date:
            order_date = fields.Date.context_today(self)
        year = fields.Date.to_date(order_date).year
        prefix = f'FACTURE/PRO FORMA/IBTC/{year}/N°'
        domain = [
            ('name', '=like', f'{prefix}%'),
            ('company_id', '=', self.env.company.id),
        ]
        last = self.search(domain, order='name desc, id desc', limit=1)
        seq = 0
        if last and last.name:
            match = re.match(rf'^FACTURE/PRO FORMA/IBTC/{year}/N°(\d+)$', last.name)
            if match:
                seq = int(match.group(1))
        return f'{prefix}{seq + 1:04d}'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name') and vals['name'] not in ('New', '/'):
                continue
            order_date = vals.get('date_order')
            vals['name'] = self._next_sobto_quotation_name(order_date)
        return super().create(vals_list)
