# -*- coding: utf-8 -*-
"""Valeurs par défaut pour les nouvelles colonnes CIMAF (section / attachement 4)."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE cmaf_invoice_line
        SET display_type = 'product'
        WHERE display_type IS NULL
        """
    )
