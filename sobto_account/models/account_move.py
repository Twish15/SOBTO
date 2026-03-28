from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    from num2words import num2words
except ImportError:
    num2words = None

MOIS_FR = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_invoice_type = fields.Selection(
        [
            ('transit', 'Transit'),
            ('transport', 'Transport'),
        ],
        string='Type de facture',
        default='transit',
        copy=False,
    )
    transport_line_ids = fields.One2many(
        'transport.invoice.line',
        'move_id',
        string='Lignes transport',
        copy=True,
    )
    amount_ht_transport = fields.Monetary(
        string='Montant HT (transport)',
        compute='_compute_transport_totals',
        currency_field='currency_id',
    )
    amount_tva_transport = fields.Monetary(
        string='TVA 18 % (transport)',
        compute='_compute_transport_totals',
        currency_field='currency_id',
    )
    amount_ttc_transport = fields.Monetary(
        string='Montant TTC (transport)',
        compute='_compute_transport_totals',
        currency_field='currency_id',
    )

    x_invoice_date_fr = fields.Char(
        string='Date (FR)',
        compute='_compute_invoice_date_fr',
        help='Date de facture formatée en français',
    )
    x_signataire = fields.Char(
        string='Signataire',
        default='Yaya OUATTARA',
        help='Nom du signataire (ex: Yaya OUATTARA)',
    )
    x_objet = fields.Char(
        string='Objet :',
    )
    x_montant_lettres = fields.Char(
        string='Montant en lettres',
        compute='_compute_montant_lettres',
        store=True,
        help='Si TVA : montant TTC en lettres et mention taxe (18 %). Sinon montant HT.',
    )

    @api.depends('transport_line_ids.montant')
    def _compute_transport_totals(self):
        for move in self:
            ht = sum(move.transport_line_ids.mapped('montant'))
            tva = ht * 0.18
            move.amount_ht_transport = ht
            move.amount_tva_transport = tva
            move.amount_ttc_transport = ht + tva

    def _get_transport_sale_taxes(self):
        self.ensure_one()
        tax = getattr(self.company_id, 'account_sale_tax_id', None)
        if tax:
            return tax
        return self.env['account.tax'].search(
            [
                ('company_id', '=', self.company_id.id),
                ('type_tax_use', '=', 'sale'),
                ('amount_type', '=', 'percent'),
            ],
            limit=1,
            order='id',
        )

    def _sync_invoice_lines_from_transport(self):
        """Recrée les lignes comptables produit à partir des lignes transport (brouillon uniquement)."""
        for move in self:
            if move.x_invoice_type != 'transport':
                continue
            if move.state != 'draft':
                continue
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue
            move.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product'
            ).unlink()
            if not move.transport_line_ids:
                continue
            tax = move._get_transport_sale_taxes()
            tax_cmd = [(6, 0, tax.ids)] if tax else [(5, 0, 0)]
            line_cmds = []
            for tl in move.transport_line_ids:
                product = tl._get_product_for_sync()
                name = product.display_name
                if tl.parcours_id:
                    name = f'{name} — {tl.parcours_id.name}'
                line_cmds.append(
                    (
                        0,
                        0,
                        {
                            'product_id': product.id,
                            'name': name,
                            'quantity': tl.quantity,
                            'price_unit': tl.taux,
                            'tax_ids': tax_cmd,
                        },
                    )
                )
            move.write({'invoice_line_ids': line_cmds})

    def write(self, vals):
        res = super().write(vals)
        if any(
            k in vals
            for k in ('x_invoice_type', 'transport_line_ids')
        ):
            for move in self:
                if move.x_invoice_type == 'transport' and move.state == 'draft':
                    move._sync_invoice_lines_from_transport()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        moves = super().create(vals_list)
        for move in moves:
            if move.x_invoice_type == 'transport' and move.state == 'draft':
                move._sync_invoice_lines_from_transport()
        return moves

    @api.depends('invoice_date')
    def _compute_invoice_date_fr(self):
        for move in self:
            if move.invoice_date:
                d = move.invoice_date
                move.x_invoice_date_fr = f"{d.day:02d} {MOIS_FR[d.month - 1]} {d.year}"
            else:
                move.x_invoice_date_fr = ''

    @api.depends('amount_untaxed', 'amount_total', 'amount_tax', 'currency_id')
    def _compute_montant_lettres(self):
        for move in self:
            if not num2words:
                move.x_montant_lettres = ''
                continue
            try:
                has_vat = bool(move.amount_tax) and move.amount_tax != 0
                if has_vat:
                    amount_val = abs(round(move.amount_total))
                    suffix = 'FCFA TTC taxe (18%)'
                else:
                    if not move.amount_untaxed:
                        move.x_montant_lettres = ''
                        continue
                    amount_val = abs(int(move.amount_untaxed))
                    suffix = 'FCFA HT'
                amount_str = num2words(amount_val, lang='fr').upper()
                num_in_paren = f"{amount_val:,}".replace(',', ' ')
                move.x_montant_lettres = (
                    f"{amount_str} ( {num_in_paren} ) {suffix}"
                )
            except Exception:
                move.x_montant_lettres = ''

    # --- Numérotation FACTURE IBTC/AAAA/ N°nnnn (réinitialisation le 1er janvier) ---

    def _get_starting_sequence(self):
        """Première valeur de la chaîne annuelle (séquence mixin Odoo)."""
        self.ensure_one()
        if self.move_type in ('out_invoice', 'out_refund') and self.journal_id.type == 'sale':
            move_date = self.date or self.invoice_date or fields.Date.context_today(self)
            year = fields.Date.to_date(move_date).year
            return f'FACTURE IBTC/{year}/ N°{0:04d}'
        return super()._get_starting_sequence()

    def _get_last_sequence_domain(self, relaxed=False):
        """Une série par année civile (1er jan. → 31 déc.), factures et avoirs partagent le compteur."""
        self.ensure_one()
        if self.move_type not in ('out_invoice', 'out_refund') or self.journal_id.type != 'sale':
            return super()._get_last_sequence_domain(relaxed)
        if not self.date or not self.journal_id:
            return 'WHERE FALSE', {}

        is_payment = self.origin_payment_id or self.env.context.get('is_payment')
        where_string = (
            'WHERE journal_id = %(journal_id)s AND name != \'/\' '
            'AND name LIKE %(name_prefix)s'
        )
        param = {'journal_id': self.journal_id.id}

        if relaxed:
            param['name_prefix'] = 'FACTURE IBTC/%'
        else:
            year = fields.Date.to_date(self.date).year
            param['name_prefix'] = f'FACTURE IBTC/{year}/ N°%'
            date_start = date(year, 1, 1)
            date_end = date(year, 12, 31)
            where_string += ' AND date BETWEEN %(date_start)s AND %(date_end)s'
            param['date_start'] = date_start
            param['date_end'] = date_end

        if self.journal_id.payment_sequence:
            if is_payment:
                where_string += ' AND origin_payment_id IS NOT NULL '
            else:
                where_string += ' AND origin_payment_id IS NULL '

        return where_string, param

    def _get_name_invoice_report(self):
        """Utilise le template SOBTO pour les factures et avoirs clients."""
        if self.move_type in ('out_invoice', 'out_refund'):
            return 'sobto_account.report_invoice_sobto'
        return super()._get_name_invoice_report()

    def action_post(self):
        for move in self:
            if (
                move.x_invoice_type == 'transport'
                and move.move_type in ('out_invoice', 'out_refund')
                and move.state == 'draft'
            ):
                move._sync_invoice_lines_from_transport()
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund') and move.partner_id:
                manquants = []
                if not move.partner_id.x_rccm:
                    manquants.append('N° RCCM')
                if not move.partner_id.x_ifu:
                    manquants.append('N° IFU')
                if manquants:
                    raise UserError(_(
                        "Impossible de valider la facture.\n\n"
                        "Les informations suivantes sont manquantes sur le client « %s » : %s.\n\n"
                        "Veuillez compléter la fiche client avant de continuer."
                    ) % (move.partner_id.name, ', '.join(manquants)))
        return super().action_post()
