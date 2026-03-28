from . import models


def post_init_hook(env):
    """TVA vente par défaut : passage 15 % → 18 % si encore à 15 %."""
    for company in env['res.company'].search([]):
        tax = getattr(company, 'account_sale_tax_id', None)
        if (
            tax
            and tax.amount_type == 'percent'
            and abs(tax.amount - 15.0) < 0.0001
        ):
            tax.sudo().write({'amount': 18.0})
