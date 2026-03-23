{
    'name': 'SOBTO - Personnalisation Facturation',
    'version': '18.0.1.0.0',
    'category': 'Accounting/Accounting',
    'summary': 'Personnalisation du module de facturation pour SOBTO',
    'author': 'SOBTO',
    'depends': ['account'],
    'data': [
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}
