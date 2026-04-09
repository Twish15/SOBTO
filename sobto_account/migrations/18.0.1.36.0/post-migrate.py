# -*- coding: utf-8 -*-
"""Valeurs par défaut pour les types de lignes personnalisées transport."""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE transport_invoice_line
        SET display_type = 'product'
        WHERE display_type IS NULL
        """
    )
