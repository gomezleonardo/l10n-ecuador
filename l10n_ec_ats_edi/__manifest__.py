# -*- coding: utf-8 -*-
{
    'name': 'Ecuador - Anexo Transaccional Simplificado (ATS)',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations/Reporting',
    'summary': 'Generación del ATS (Anexo Transaccional Simplificado) para el SRI de Ecuador',
    'description': """
        Módulo para la generación del ATS del SRI Ecuador.
        Compatible con la localización oficial de Odoo (l10n_ec) y la localización OCA.

        Funcionalidades:
        - Generación del XML del ATS validado contra at.xsd (estructura SRI)
        - Vista previa en pantalla con detalle de compras y ventas
        - Exportación XLSX con hojas separadas por sección (Compras, Ventas, Retenciones, etc.)
        - Soporte para declaración mensual y semestral (RIMPE microempresas)
        - Módulos: Compras, Ventas, Exportaciones, Anulados, Reembolsos
        - Retenciones de IVA y de Impuesto a la Renta (emitidas y recibidas)
        - Formas de pago y bancarización (>=USD 500 desde dic 2023)
        - Comprobantes electrónicos: excluidos automáticamente si aplica
        - Tipos de identificación ATS tomados del tipo de identificación LATAM
          (l10n_ec / l10n_ec_base), sin módulos adicionales de mapeo

        Campos clave del XML:
        - detalleCompras: por proveedor y documento
        - detalleVentas: por cliente y comprobante
        - detalleRetenciones: IVA e IR retenidos/recibidos
        - codSustento: código de sustento tributario (01-19)
    """,
    'author': 'OCA, Francisco Silva, Leonardo Gomez',
    'website': 'https://github.com/OCA/l10n-ecuador',
    'license': 'AGPL-3',
    'depends': [
        'account',       # Community
        'l10n_ec',       # Localización oficial Ecuador
        'l10n_ec_base',  # Tipos de identificación y campos base de la localización
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ats_catalogo_data.xml',
        'wizard/ec_ats_wizard_views.xml',
        'views/ec_ats_report_run_views.xml',
        'report/ec_ats_report_pdf.xml',
    ],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'auto_install': False,
    'installable': True,
    'application': False,
}
