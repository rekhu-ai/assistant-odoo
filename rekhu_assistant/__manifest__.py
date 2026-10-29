{
    'name': 'Rekhu Assistant',
    'summary': 'An AI assistant inside Odoo that finds records, answers from your help and does the work, with each user\'s own access rights',
    'version': '19.0.1.0.3',
    'category': 'Productivity',
    'author': 'Rekhu',
    'website': 'https://rekhu.com/products/assistant',
    'support': 'hello@rekhu.com',
    'images': ['static/description/banner.png'],
    'license': 'Other proprietary',
    'depends': ['web', 'mail'],
    'external_dependencies': {'python': ['requests']},
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron.xml',
        'views/rekhu_help_views.xml',
        'views/rekhu_setup_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'rekhu_assistant/static/lib/rekhu-assistant.js',
            'rekhu_assistant/static/src/assistant_service.js',
        ],
    },
}
