# -*- coding: utf-8 -*-
"""Renomme x_cmaf_apply_tva -> x_apply_tva (TVA par facture pour tous les types SOBTO)."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'account_move'
          AND column_name = 'x_cmaf_apply_tva'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'account_move'
          AND column_name = 'x_apply_tva'
        """
    )
    if cr.fetchone():
        cr.execute(
            """
            UPDATE account_move
            SET x_apply_tva = COALESCE(x_cmaf_apply_tva, x_apply_tva, TRUE)
            """
        )
        cr.execute("ALTER TABLE account_move DROP COLUMN x_cmaf_apply_tva")
    else:
        cr.execute(
            "ALTER TABLE account_move RENAME COLUMN x_cmaf_apply_tva TO x_apply_tva"
        )
