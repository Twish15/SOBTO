# -*- coding: utf-8 -*-
"""
Migration 18.0.1.4.0: Forcer le template SOBTO pour tous les rapports facture.
Exécuté lors de la mise à jour du module.
"""


def migrate(cr, version):
    if not version:
        return

    # Forcer le template SOBTO pour les rapports facture (par nom de template actuel)
    cr.execute("""
        UPDATE ir_act_report
        SET report_name = 'sobto_account.report_invoice_sobto'
        WHERE report_name IN ('account.report_invoice', 'account.report_invoice_with_payments')
    """)
