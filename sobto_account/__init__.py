from . import models


def post_init_hook(env):
    """Force tous les rapports facture à utiliser le template SOBTO (au cas où l'override XML échoue)."""
    Report = env['ir.actions.report']
    invoice_reports = Report.search([
        ('model', '=', 'account.move'),
        ('report_type', '=', 'qweb-pdf'),
        ('report_name', 'in', [
            'account.report_invoice',
            'account.report_invoice_with_payments',
        ]),
    ])
    if invoice_reports:
        invoice_reports.write({'report_name': 'sobto_account.report_invoice_sobto'})
