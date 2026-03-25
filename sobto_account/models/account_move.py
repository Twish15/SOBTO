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
        string='Objet',
        help='Objet de la facture (ex: TRANSPORT D\'HYDROCARBURES)',
    )
    x_montant_lettres = fields.Char(
        string='Montant en lettres',
        compute='_compute_montant_lettres',
        store=True,
        help='Montant HT exprimé en toutes lettres (FCFA)',
    )

    @api.depends('invoice_date')
    def _compute_invoice_date_fr(self):
        for move in self:
            if move.invoice_date:
                d = move.invoice_date
                move.x_invoice_date_fr = f"{d.day:02d} {MOIS_FR[d.month - 1]} {d.year}"
            else:
                move.x_invoice_date_fr = ''

    @api.depends('amount_untaxed', 'currency_id')
    def _compute_montant_lettres(self):
        for move in self:
            if num2words and move.amount_untaxed:
                try:
                    amount_int = int(move.amount_untaxed)
                    amount_str = num2words(amount_int, lang='fr').upper()
                    formatted = f"{amount_int:,}".replace(',', ' ')
                    move.x_montant_lettres = (
                        f"{amount_str} {formatted} FCFA HT"
                    )
                except Exception:
                    move.x_montant_lettres = ''
            else:
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
