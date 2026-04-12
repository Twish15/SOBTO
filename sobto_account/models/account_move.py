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

# Libellés d'objet par défaut (modifiables sur la facture)
DEFAULT_X_OBJET_BY_TYPE = {
    'transit': 'FRAIS DE TRANSIT (CODE 404697)',
    'transport': "TRANSPORT D'HYDROCARBURES (CODE 404697)",
    'cmaf': 'TRANSPORT DE TUFF (HOLY MOUNTAIN - OUAGADOUGOU)',
    'simple': 'FACTURATION (CODE 404697)',
}


class AccountMove(models.Model):
    _inherit = 'account.move'

    x_invoice_type = fields.Selection(
        [
            ('transit', 'Transit'),
            ('simple', 'Facture simple'),
            ('transport', 'Transport'),
            ('cmaf', 'CIMAF'),
        ],
        string='Type de facture',
        default='transit',
        copy=False,
    )
    x_cmaf_attachment_1 = fields.Char(string='Attachement ligne 1')
    x_cmaf_attachment_2 = fields.Char(string='Attachement ligne 2')
    x_cmaf_attachment_3 = fields.Char(string='Attachement ligne 3')
    x_cmaf_attachment_4 = fields.Char(string='Attachement ligne 4')
    x_apply_tva = fields.Boolean(
        string='Appliquer la TVA',
        default=True,
        help='Par facture : si désactivé, lignes sans TVA (brouillon) et PDF sans lignes de taxes / TTC.',
    )
    transport_line_ids = fields.One2many(
        'transport.invoice.line',
        'move_id',
        string='Lignes transport',
        copy=True,
    )
    cmaf_line_ids = fields.One2many(
        'cmaf.invoice.line',
        'move_id',
        string='Lignes CIMAF',
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
    amount_ht_cmaf = fields.Monetary(
        string='TOTAL GENERAL HT (CIMAF)',
        compute='_compute_cmaf_totals',
        currency_field='currency_id',
    )
    amount_tva_cmaf = fields.Monetary(
        string='TVA 18 % (CIMAF)',
        compute='_compute_cmaf_totals',
        currency_field='currency_id',
    )
    amount_ttc_cmaf = fields.Monetary(
        string='TOTAL GENERAL TTC (CIMAF)',
        compute='_compute_cmaf_totals',
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
        help='TTC en lettres si « Appliquer la TVA » est coché, sinon HT.',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        # fields_list peut être None (tous les champs) : ne pas utiliser « in fields_list » seul.
        load_date = fields_list is None or 'invoice_date' in fields_list
        if load_date and res.get('move_type') in (
            'out_invoice',
            'out_refund',
            'in_invoice',
            'in_refund',
        ) and not res.get('invoice_date'):
            res['invoice_date'] = fields.Date.context_today(self)
        load_objet = fields_list is None or 'x_objet' in fields_list
        if load_objet and not res.get('x_objet'):
            inv_type = res.get('x_invoice_type', 'transit')
            res['x_objet'] = self._get_default_x_objet(inv_type)
        return res

    @api.model
    def _get_default_x_objet(self, invoice_type):
        return DEFAULT_X_OBJET_BY_TYPE.get(
            invoice_type, DEFAULT_X_OBJET_BY_TYPE['transit']
        )

    @api.onchange('x_invoice_type')
    def _onchange_x_invoice_type_objet(self):
        if self.x_invoice_type:
            self.x_objet = self._get_default_x_objet(self.x_invoice_type)

    @api.depends('transport_line_ids.montant', 'x_apply_tva', 'x_invoice_type')
    def _compute_transport_totals(self):
        for move in self:
            ht = sum(move.transport_line_ids.mapped('montant'))
            move.amount_ht_transport = ht
            if move.x_invoice_type == 'transport' and not move.x_apply_tva:
                move.amount_tva_transport = 0.0
                move.amount_ttc_transport = ht
            else:
                tva = ht * 0.18
                move.amount_tva_transport = tva
                move.amount_ttc_transport = ht + tva

    @api.depends(
        'cmaf_line_ids.total_net',
        'cmaf_line_ids.display_type',
        'x_apply_tva',
        'x_invoice_type',
    )
    def _compute_cmaf_totals(self):
        for move in self:
            product_lines = move.cmaf_line_ids.filtered(
                lambda l: l.display_type == 'product'
            )
            ht = sum(product_lines.mapped('total_net'))
            move.amount_ht_cmaf = ht
            if move.x_invoice_type == 'cmaf' and not move.x_apply_tva:
                move.amount_tva_cmaf = 0.0
                move.amount_ttc_cmaf = ht
            else:
                tva = ht * 0.18
                move.amount_tva_cmaf = tva
                move.amount_ttc_cmaf = ht + tva

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
                lambda l: l.display_type in ('product', 'line_section', 'line_note')
            ).unlink()
            if not move.transport_line_ids:
                continue
            tax = move._get_transport_sale_taxes()
            if move.x_apply_tva:
                tax_cmd = [(6, 0, tax.ids)] if tax else [(5, 0, 0)]
            else:
                tax_cmd = [(5, 0, 0)]
            line_cmds = []
            for tl in move.transport_line_ids:
                if tl.display_type == 'line_section':
                    line_cmds.append(
                        (
                            0,
                            0,
                            {
                                'sequence': tl.sequence,
                                'display_type': 'line_section',
                                'name': tl.name or ' ',
                            },
                        )
                    )
                    continue
                product = tl._get_product_for_sync()
                name = product.display_name
                if tl.parcours_id:
                    name = f'{name} — {tl.parcours_id.name}'
                line_cmds.append(
                    (
                        0,
                        0,
                        {
                            'sequence': tl.sequence,
                            'product_id': product.id,
                            'product_uom_id': product.uom_id.id,
                            'name': name,
                            'quantity': tl.quantity,
                            'price_unit': tl.taux,
                            'tax_ids': tax_cmd,
                        },
                    )
                )
            move.write({'invoice_line_ids': line_cmds})

    def _sync_invoice_lines_from_cmaf(self):
        """Recrée les lignes comptables à partir des lignes CIMAF (brouillon uniquement)."""
        for move in self:
            if move.x_invoice_type != 'cmaf':
                continue
            if move.state != 'draft':
                continue
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue
            move.invoice_line_ids.filtered(
                lambda l: l.display_type in ('product', 'line_section', 'line_note')
            ).unlink()
            if not move.cmaf_line_ids:
                continue
            tax = move._get_transport_sale_taxes()
            if move.x_apply_tva:
                tax_cmd = [(6, 0, tax.ids)] if tax else [(5, 0, 0)]
            else:
                tax_cmd = [(5, 0, 0)]
            line_cmds = []
            for cl in move.cmaf_line_ids:
                if cl.display_type == 'line_section':
                    line_cmds.append(
                        (
                            0,
                            0,
                            {
                                'sequence': cl.sequence,
                                'display_type': 'line_section',
                                'name': cl.name or ' ',
                            },
                        )
                    )
                    continue
                product = cl._get_product_for_sync()
                parts = [product.display_name]
                if cl.camion_id:
                    parts.append(cl.camion_id.name)
                name = ' — '.join(parts)
                line_cmds.append(
                    (
                        0,
                        0,
                        {
                            'sequence': cl.sequence,
                            'product_id': product.id,
                            'product_uom_id': product.uom_id.id,
                            'name': name,
                            'quantity': 1.0,
                            'price_unit': cl.total_net,
                            'tax_ids': tax_cmd,
                        },
                    )
                )
            move.write({'invoice_line_ids': line_cmds})

    def _sobto_apply_taxes_on_transit_lines(self):
        """Applique ou retire les taxes sur les lignes produit (Transit, brouillon)."""
        for move in self:
            if move.x_invoice_type != 'transit':
                continue
            if move.state != 'draft':
                continue
            if move.move_type not in ('out_invoice', 'out_refund'):
                continue
            lines = move.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product' and l.product_id
            )
            if not lines:
                continue
            if not move.x_apply_tva:
                lines.with_context(skip_sobto_tax_sync=True).write(
                    {'tax_ids': [(5, 0, 0)]}
                )
                continue
            for line in lines:
                taxes = line.product_id.taxes_id.filtered(
                    lambda t: t.company_id == move.company_id
                )
                if move.fiscal_position_id:
                    taxes = move.fiscal_position_id.map_tax(taxes)
                line.with_context(skip_sobto_tax_sync=True).write(
                    {'tax_ids': [(6, 0, taxes.ids)]}
                )

    def write(self, vals):
        if self.env.context.get('skip_sobto_tax_sync'):
            return super().write(vals)
        res = super().write(vals)
        if any(
            k in vals
            for k in (
                'x_invoice_type',
                'transport_line_ids',
                'cmaf_line_ids',
                'x_apply_tva',
            )
        ):
            for move in self:
                if move.x_invoice_type == 'transport' and move.state == 'draft':
                    move._sync_invoice_lines_from_transport()
                if move.x_invoice_type == 'cmaf' and move.state == 'draft':
                    move._sync_invoice_lines_from_cmaf()
        if any(
            k in vals
            for k in ('x_apply_tva', 'x_invoice_type', 'invoice_line_ids')
        ):
            to_transit = self.filtered(
                lambda m: m.state == 'draft' and m.x_invoice_type == 'transit'
            )
            if to_transit:
                to_transit._sobto_apply_taxes_on_transit_lines()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            inv_type = vals.get('x_invoice_type', 'transit')
            if not vals.get('x_objet'):
                vals['x_objet'] = self._get_default_x_objet(inv_type)
        moves = super().create(vals_list)
        for move in moves:
            if move.x_invoice_type == 'transport' and move.state == 'draft':
                move._sync_invoice_lines_from_transport()
            if move.x_invoice_type == 'cmaf' and move.state == 'draft':
                move._sync_invoice_lines_from_cmaf()
            if move.x_invoice_type == 'transit' and move.state == 'draft':
                move._sobto_apply_taxes_on_transit_lines()
        return moves

    @api.depends('invoice_date')
    def _compute_invoice_date_fr(self):
        for move in self:
            if move.invoice_date:
                d = move.invoice_date
                move.x_invoice_date_fr = f"{d.day:02d} {MOIS_FR[d.month - 1]} {d.year}"
            else:
                move.x_invoice_date_fr = ''

    @api.depends(
        'amount_untaxed',
        'amount_total',
        'amount_tax',
        'currency_id',
        'x_invoice_type',
        'x_apply_tva',
    )
    def _compute_montant_lettres(self):
        for move in self:
            if not num2words:
                move.x_montant_lettres = ''
                continue
            try:
                # Toutes factures SOBTO : TTC en lettres si TVA demandée, sinon HT
                if move.x_apply_tva:
                    if not move.amount_total:
                        move.x_montant_lettres = ''
                        continue
                    amount_val = abs(round(move.amount_total))
                    suffix = 'Francs CFA TTC'
                else:
                    if not move.amount_untaxed:
                        move.x_montant_lettres = ''
                        continue
                    amount_val = abs(round(move.amount_untaxed))
                    suffix = 'Francs CFA HT'
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
            if (
                move.x_invoice_type == 'cmaf'
                and move.move_type in ('out_invoice', 'out_refund')
                and move.state == 'draft'
            ):
                move._sync_invoice_lines_from_cmaf()
            if (
                move.x_invoice_type == 'transit'
                and move.move_type in ('out_invoice', 'out_refund')
                and move.state == 'draft'
            ):
                move._sobto_apply_taxes_on_transit_lines()
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
