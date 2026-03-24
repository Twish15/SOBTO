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
                        f"{amount_str} ({formatted} FCFA HT)"
                    )
                except Exception:
                    move.x_montant_lettres = ''
            else:
                move.x_montant_lettres = ''

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
