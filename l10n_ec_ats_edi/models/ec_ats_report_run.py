# -*- coding: utf-8 -*-
import base64
import json
from calendar import monthrange
from datetime import datetime
from html import escape

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class EcAtsReportRun(models.Model):
    _name = 'ec.ats.report.run'
    _description = 'ATS Ecuador - Ejecución'
    _order = 'id desc'

    name = fields.Char(string='Descripción', required=True, default='Nueva ejecución ATS')
    state = fields.Selection(
        [('draft', 'Borrador'), ('generated', 'Generado')],
        string='Estado',
        default='draft',
        required=True,
    )
    generated_at = fields.Datetime(string='Generado en', readonly=True)

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

    include_electronic = fields.Boolean(
        string='Incluir documentos electrónicos en módulo Ventas',
        default=False,
        help='Si está marcado, incluye facturas electrónicas autorizadas en ventas. '
             'En general debe estar desmarcado.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Empresa',
        default=lambda self: self.env.company,
        required=True,
    )

    fecha_desde = fields.Date(compute='_compute_fechas', store=True, string='Desde')
    fecha_hasta = fields.Date(compute='_compute_fechas', store=True, string='Hasta')

    estado = fields.Char(string='Mensaje', readonly=True)
    vista_previa_html = fields.Html(readonly=True)
    resultado_json = fields.Text(readonly=True)

    archivo_xml_nombre = fields.Char(readonly=True)
    archivo_xml_datos = fields.Binary(readonly=True, attachment=True)
    archivo_xlsx_nombre = fields.Char(readonly=True)
    archivo_xlsx_datos = fields.Binary(readonly=True, attachment=True)

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

    @api.constrains('anio')
    def _check_anio(self):
        for rec in self:
            anio = int(rec.anio or 0)
            if not (2000 <= anio <= 2099):
                raise UserError(_('El año debe estar entre 2000 y 2099.'))

    def action_generar(self):
        for rec in self:
            ats_data = rec._generate_ats_data()
            period_label = ats_data.get('period_label', rec._period_label())
            rec.write({
                'name': f"ATS - {period_label} - {rec.company_id.name}",
                'state': 'generated',
                'generated_at': fields.Datetime.now(),
                'estado': rec._status_message(ats_data),
                'vista_previa_html': rec._build_preview_html(ats_data),
                'resultado_json': json.dumps(rec._snapshot_for_json(ats_data), ensure_ascii=False),
                'archivo_xml_nombre': False,
                'archivo_xml_datos': False,
                'archivo_xlsx_nombre': False,
                'archivo_xlsx_datos': False,
            })
        return True

    def action_exportar_xml(self):
        self.ensure_one()
        ats_data = self._generate_ats_data()
        mes_str = str(self.fecha_desde)[5:7]
        anio_str = self._to_plain_year(str(self.fecha_desde)[:4])
        filename = f'ATS_{self.company_id.vat}_{anio_str}{mes_str}.xml'
        xml_bytes = ats_data.get('xml', b'')
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode('utf-8')
        self.write({
            'archivo_xml_nombre': filename,
            'archivo_xml_datos': base64.b64encode(xml_bytes),
            'estado': '✓ XML generado correctamente.',
        })
        return self._download_binary_action('archivo_xml_datos', filename)

    def action_exportar_xlsx(self):
        self.ensure_one()
        ats_data = self._get_cached_or_generate()
        mes_str = str(self.fecha_desde)[5:7]
        anio_str = self._to_plain_year(str(self.fecha_desde)[:4])
        filename = f'ATS_{self.company_id.vat}_{anio_str}{mes_str}.xlsx'
        xlsx_bytes = self.env['ec.ats.report'].generate_xlsx(ats_data)
        self.write({
            'archivo_xlsx_nombre': filename,
            'archivo_xlsx_datos': base64.b64encode(xlsx_bytes),
            'estado': '✓ XLSX generado correctamente.',
        })
        return self._download_binary_action('archivo_xlsx_datos', filename)

    def action_exportar_pdf(self):
        self.ensure_one()
        if self.state != 'generated' or not self.vista_previa_html:
            self.action_generar()
        return self.env.ref('l10n_ec_ats_edi.action_report_ec_ats_run_pdf').report_action(self)

    def action_exportar_ambos(self):
        self.ensure_one()
        ats_data = self._generate_ats_data()
        mes_str = str(self.fecha_desde)[5:7]
        anio_str = self._to_plain_year(str(self.fecha_desde)[:4])
        base = f'ATS_{self.company_id.vat}_{anio_str}{mes_str}'
        xml_bytes = ats_data.get('xml', b'')
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode('utf-8')
        xlsx_bytes = self.env['ec.ats.report'].generate_xlsx(ats_data)
        self.write({
            'archivo_xml_nombre': f'{base}.xml',
            'archivo_xml_datos': base64.b64encode(xml_bytes),
            'archivo_xlsx_nombre': f'{base}.xlsx',
            'archivo_xlsx_datos': base64.b64encode(xlsx_bytes),
            'estado': '✓ XML y XLSX generados correctamente.',
        })
        return self._download_binary_action('archivo_xml_datos', f'{base}.xml')

    def _generate_ats_data(self):
        self.ensure_one()
        options = {
            'date_from': str(self.fecha_desde),
            'date_to': str(self.fecha_hasta),
            'company_id': self.company_id.id,
            'include_electronic': self.include_electronic,
            'semestral': self.tipo_periodo != 'mensual',
        }
        data = self.env['ec.ats.report'].generate_ats(options)
        data['period_label'] = self._period_label()
        return data

    def _get_cached_or_generate(self):
        self.ensure_one()
        if self.resultado_json:
            return json.loads(self.resultado_json)
        return self._generate_ats_data()

    def _status_message(self, ats_data):
        compras = len(ats_data.get('compras', []))
        ventas = len(ats_data.get('ventas', []))
        return f'✓ Generado: {compras} documentos de compra, {ventas} documentos de venta.'

    def _snapshot_for_json(self, ats_data):
        snapshot = dict(ats_data or {})
        snapshot.pop('xml', None)
        return snapshot

    def _build_preview_html(self, ats_data):
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
            f"<p><i>Generado: {escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</i></p>"
            "</div>"
        )

    def _period_label(self):
        self.ensure_one()
        meses = {
            '01': 'Enero', '02': 'Febrero', '03': 'Marzo',
            '04': 'Abril', '05': 'Mayo', '06': 'Junio',
            '07': 'Julio', '08': 'Agosto', '09': 'Septiembre',
            '10': 'Octubre', '11': 'Noviembre', '12': 'Diciembre',
        }
        anio = self._to_plain_year(self.anio)
        if self.tipo_periodo == 'mensual':
            return f"{meses.get(self.mes or '01', '')} {anio}"
        if self.tipo_periodo == 'semestral_1':
            return f"Ene-Jun {anio}"
        if self.tipo_periodo == 'semestral_2':
            return f"Jul-Dic {anio}"
        return anio

    def _download_binary_action(self, field_name, filename):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/{}/{}/{}/{}?download=true'.format(
                self._name, self.id, field_name, filename or 'archivo'
            ),
            'target': 'self',
        }

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
    def _to_plain_year(value):
        try:
            return str(int(float(str(value).strip())))
        except (TypeError, ValueError):
            return str(value).strip()

    @staticmethod
    def _safe_int(value, default):
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return int(default)
