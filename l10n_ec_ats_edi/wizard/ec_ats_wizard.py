# -*- coding: utf-8 -*-
"""
wizard/ec_ats_wizard.py
=======================
Wizard para configurar y generar el ATS del SRI Ecuador.
"""
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from calendar import monthrange
import base64
from html import escape


class EcAtsWizard(models.TransientModel):
    _name = 'ec.ats.wizard'
    _description = 'Wizard - Generación ATS Ecuador'

    # ── Período ──
    tipo_periodo = fields.Selection([
        ('mensual', 'Mensual'),
        ('semestral_1', 'Semestral - 1er Semestre (Ene–Jun)'),
        ('semestral_2', 'Semestral - 2do Semestre (Jul–Dic)'),
    ], string='Tipo de período', default='mensual', required=True)

    anio = fields.Selection(
        selection='_year_selection',
        string='Año',
        default=lambda self: str(fields.Date.today().year),
        required=True,
    )
    mes = fields.Selection([
        ('01', 'Enero'), ('02', 'Febrero'), ('03', 'Marzo'),
        ('04', 'Abril'), ('05', 'Mayo'), ('06', 'Junio'),
        ('07', 'Julio'), ('08', 'Agosto'), ('09', 'Septiembre'),
        ('10', 'Octubre'), ('11', 'Noviembre'), ('12', 'Diciembre'),
    ], string='Mes', default=lambda self: f'{fields.Date.today().month:02d}')

    # ── Opciones ──
    include_electronic = fields.Boolean(
        string='Incluir documentos electrónicos en módulo Ventas',
        default=False,
        help='Si está marcado, incluye facturas electrónicas autorizadas en el módulo de '
             'ventas. En general debe estar desmarcado, ya que el SRI ya las tiene por '
             'el proceso de autorización. Marcar solo si tu DIMM lo requiere explícitamente.',
    )
    company_id = fields.Many2one(
        'res.company', string='Empresa',
        default=lambda self: self.env.company,
        required=True,
    )

    # ── Formato de salida ──
    formato_exportacion = fields.Selection([
        ('xml', 'XML para DIMM SRI (principal)'),
        ('xlsx', 'Excel XLSX (revisión)'),
        ('ambos', 'Ambos (XML + XLSX)'),
    ], string='Formato de exportación', default='xml', required=True)

    # ── Fechas calculadas ──
    fecha_desde = fields.Date(compute='_compute_fechas', string='Desde')
    fecha_hasta = fields.Date(compute='_compute_fechas', string='Hasta')

    @api.depends('tipo_periodo', 'anio', 'mes')
    def _compute_fechas(self):
        for rec in self:
            anio = self._safe_int(rec.anio, fields.Date.today().year)
            if rec.tipo_periodo == 'mensual':
                mes = self._safe_int(rec.mes, 1)
                ultimo = monthrange(anio, mes)[1]
                rec.fecha_desde = f'{anio}-{mes:02d}-01'
                rec.fecha_hasta = f'{anio}-{mes:02d}-{ultimo:02d}'
            elif rec.tipo_periodo == 'semestral_1':
                rec.fecha_desde = f'{anio}-01-01'
                rec.fecha_hasta = f'{anio}-06-30'
            elif rec.tipo_periodo == 'semestral_2':
                rec.fecha_desde = f'{anio}-07-01'
                rec.fecha_hasta = f'{anio}-12-31'
            else:
                rec.fecha_desde = False
                rec.fecha_hasta = False

    # ── Resultado ──
    archivo_xml_nombre = fields.Char(readonly=True)
    archivo_xml_datos = fields.Binary(readonly=True)
    archivo_xlsx_nombre = fields.Char(readonly=True)
    archivo_xlsx_datos = fields.Binary(readonly=True)
    estado = fields.Char(readonly=True)
    vista_previa_html = fields.Html(readonly=True)

    def action_generar(self):
        """Genera la vista previa del ATS y abre la vista de resultados."""
        self.ensure_one()
        ats_data = self._generate_ats_data()

        # Preparar escritura
        write_vals = {}
        total_compras = len(ats_data.get('compras', []))
        total_ventas = len(ats_data.get('ventas', []))
        write_vals['estado'] = (
            f'✓ Generado: {total_compras} documentos de compra, '
            f'{total_ventas} documentos de venta.'
        )
        write_vals['vista_previa_html'] = self._build_preview_html(ats_data)
        write_vals['archivo_xml_datos'] = False
        write_vals['archivo_xml_nombre'] = False
        write_vals['archivo_xlsx_datos'] = False
        write_vals['archivo_xlsx_nombre'] = False

        self.write(write_vals)
        return self._open_result_view()

    def action_exportar_xml(self):
        self.ensure_one()
        ats_data = self._generate_ats_data()
        mes_str = str(self.fecha_desde)[5:7]
        anio_str = self._to_plain_year(str(self.fecha_desde)[:4])
        nombre_base = f'ATS_{self.company_id.vat}_{anio_str}{mes_str}'
        xml_bytes = ats_data.get('xml', b'')
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode('utf-8')
        self.write({
            'archivo_xml_datos': base64.b64encode(xml_bytes),
            'archivo_xml_nombre': f'{nombre_base}.xml',
            'estado': '✓ XML generado correctamente.',
        })
        return self._download_binary_action('archivo_xml_datos', f'{nombre_base}.xml')

    def action_exportar_xlsx(self):
        self.ensure_one()
        ats_data = self._generate_ats_data()
        mes_str = str(self.fecha_desde)[5:7]
        anio_str = self._to_plain_year(str(self.fecha_desde)[:4])
        nombre_base = f'ATS_{self.company_id.vat}_{anio_str}{mes_str}'
        generador = self.env['ec.ats.report']
        xlsx_bytes = generador.generate_xlsx(ats_data)
        self.write({
            'archivo_xlsx_datos': base64.b64encode(xlsx_bytes),
            'archivo_xlsx_nombre': f'{nombre_base}.xlsx',
            'estado': '✓ XLSX generado correctamente.',
        })
        return self._download_binary_action('archivo_xlsx_datos', f'{nombre_base}.xlsx')

    def action_exportar_ambos(self):
        self.ensure_one()
        ats_data = self._generate_ats_data()
        mes_str = str(self.fecha_desde)[5:7]
        anio_str = self._to_plain_year(str(self.fecha_desde)[:4])
        nombre_base = f'ATS_{self.company_id.vat}_{anio_str}{mes_str}'
        xml_bytes = ats_data.get('xml', b'')
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode('utf-8')
        generador = self.env['ec.ats.report']
        xlsx_bytes = generador.generate_xlsx(ats_data)
        self.write({
            'archivo_xml_datos': base64.b64encode(xml_bytes),
            'archivo_xml_nombre': f'{nombre_base}.xml',
            'archivo_xlsx_datos': base64.b64encode(xlsx_bytes),
            'archivo_xlsx_nombre': f'{nombre_base}.xlsx',
            'estado': '✓ XML y XLSX generados correctamente.',
        })
        return self._open_result_view()

    def _generate_ats_data(self):
        options = {
            'date_from': str(self.fecha_desde),
            'date_to': str(self.fecha_hasta),
            'company_id': self.company_id.id,
            'include_electronic': self.include_electronic,
            'semestral': self.tipo_periodo != 'mensual',
        }
        return self.env['ec.ats.report'].generate_ats(options)

    def _open_result_view(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ec.ats.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('l10n_ec_ats_edi.view_ec_ats_wizard_result_form').id,
            'target': 'new',
        }

    def _download_binary_action(self, field_name, filename):
        self.ensure_one()
        safe_name = filename or 'archivo'
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/{}/{}/{}/{}?download=true'.format(
                self._name, self.id, field_name, safe_name
            ),
            'target': 'self',
        }

    def _build_preview_html(self, ats_data):
        """Construye una vista previa simple del ATS para consulta en pantalla."""
        totales = ats_data.get('totales', {})
        compras = ats_data.get('compras', [])
        ventas = ats_data.get('ventas', [])

        def fmt(v):
            return f"{float(v or 0.0):,.2f}"

        compras_rows = []
        for row in compras[:20]:
            compras_rows.append(
                "<tr>"
                f"<td>{escape(str(row.get('fechaEmision', '')))}</td>"
                f"<td>{escape(str(row.get('idProv', '')))}</td>"
                f"<td>{escape(str(row.get('_proveedor_nombre', '')))}</td>"
                f"<td style='text-align:right'>{fmt(row.get('_total', 0.0))}</td>"
                "</tr>"
            )
        ventas_rows = []
        for row in ventas[:20]:
            ventas_rows.append(
                "<tr>"
                f"<td>{escape(str(row.get('_fecha', '')))}</td>"
                f"<td>{escape(str(row.get('idCliente', '')))}</td>"
                f"<td>{escape(str(row.get('_cliente_nombre', '')))}</td>"
                f"<td style='text-align:right'>{fmt(row.get('_total', 0.0))}</td>"
                "</tr>"
            )

        compras_html = "".join(compras_rows) or "<tr><td colspan='4'>Sin datos</td></tr>"
        ventas_html = "".join(ventas_rows) or "<tr><td colspan='4'>Sin datos</td></tr>"

        return (
            "<div>"
            "<h3>Resumen ATS</h3>"
            "<table class='table table-sm table-bordered'>"
            f"<tr><td><b>Total compras (base)</b></td><td style='text-align:right'>{fmt(totales.get('total_compras_base', 0.0))}</td></tr>"
            f"<tr><td><b>Total IVA compras</b></td><td style='text-align:right'>{fmt(totales.get('total_iva_compras', 0.0))}</td></tr>"
            f"<tr><td><b>Total ventas (base)</b></td><td style='text-align:right'>{fmt(totales.get('total_ventas_base', 0.0))}</td></tr>"
            f"<tr><td><b>Total IVA ventas</b></td><td style='text-align:right'>{fmt(totales.get('total_iva_ventas', 0.0))}</td></tr>"
            f"<tr><td><b>Documentos compra</b></td><td style='text-align:right'>{int(totales.get('num_compras', 0) or 0)}</td></tr>"
            f"<tr><td><b>Documentos venta</b></td><td style='text-align:right'>{int(totales.get('num_ventas', 0) or 0)}</td></tr>"
            "</table>"
            "<h4>Compras (primeros 20)</h4>"
            "<table class='table table-sm table-bordered'>"
            "<thead><tr><th>Fecha</th><th>ID</th><th>Proveedor</th><th style='text-align:right'>Total</th></tr></thead>"
            f"<tbody>{compras_html}</tbody>"
            "</table>"
            "<h4>Ventas (primeros 20)</h4>"
            "<table class='table table-sm table-bordered'>"
            "<thead><tr><th>Fecha</th><th>ID</th><th>Cliente</th><th style='text-align:right'>Total</th></tr></thead>"
            f"<tbody>{ventas_html}</tbody>"
            "</table>"
            "<p><i>Los archivos XML/XLSX siguen disponibles para descarga.</i></p>"
            "</div>"
        )

    @staticmethod
    def _to_plain_year(value):
        """Normaliza el año a entero puro sin formato (ej. '2026')."""
        try:
            return str(int(float(str(value).strip())))
        except (TypeError, ValueError):
            return str(value).strip()

    @api.model
    def _year_selection(self):
        company_id = self.env.context.get('default_company_id') or self.env.company.id
        self.env.cr.execute("""
            SELECT DISTINCT EXTRACT(YEAR FROM m.date)::int AS y
            FROM account_move m
            WHERE m.state = 'posted'
              AND m.company_id = %s
              AND m.date IS NOT NULL
              AND m.move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
            ORDER BY y DESC
        """, (company_id,))
        years = [str(row[0]) for row in self.env.cr.fetchall() if row and row[0]]
        if not years:
            years = [str(fields.Date.today().year)]
        return [(y, y) for y in years]

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return int(default)
