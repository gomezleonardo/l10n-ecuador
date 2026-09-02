# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request, content_disposition
import json


class EcAtsController(http.Controller):

    @http.route('/l10n_ec_ats/xml', type='http', auth='user', methods=['GET'])
    def download_ats_xml(self, date_from=None, date_to=None, company_id=None, **kwargs):
        """
        Descarga el XML del ATS para el período indicado.
        GET /l10n_ec_ats/xml?date_from=2025-01-01&date_to=2025-01-31
        """
        if not date_from or not date_to:
            return request.make_response(
                json.dumps({'error': 'Parámetros date_from y date_to requeridos'}),
                headers=[('Content-Type', 'application/json')], status=400,
            )

        company = (request.env['res.company'].browse(int(company_id))
                   if company_id else request.env.company)

        options = {
            'date_from': date_from,
            'date_to': date_to,
            'company_id': company.id,
            'include_electronic': kwargs.get('include_electronic', 'false').lower() == 'true',
            'semestral': kwargs.get('semestral', 'false').lower() == 'true',
        }

        generador = request.env['ec.ats.report']
        ats_data = generador.generate_ats(options)
        xml_bytes = ats_data.get('xml', b'')
        if isinstance(xml_bytes, str):
            xml_bytes = xml_bytes.encode('utf-8')

        mes_str = date_from[5:7]
        anio_str = date_from[:4]
        filename = f'ATS_{company.vat}_{anio_str}{mes_str}.xml'

        return request.make_response(
            xml_bytes,
            headers=[
                ('Content-Type', 'application/xml; charset=utf-8'),
                ('Content-Disposition', content_disposition(filename)),
                ('Content-Length', len(xml_bytes)),
            ],
        )
