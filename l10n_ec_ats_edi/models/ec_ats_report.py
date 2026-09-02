# -*- coding: utf-8 -*-
"""
models/ec_ats_report.py
=======================
Generador del Anexo Transaccional Simplificado (ATS) para el SRI de Ecuador.

El ATS es un XML transaccional: no es un resumen de casilleros como el 104,
sino que reporta CADA DOCUMENTO (factura, retención, nota de crédito) con
su detalle completo.

ESTRUCTURA DEL XML ATS (at.xsd):
────────────────────────────────
<iva>
  <TipoIDInformante>...</TipoIDInformante>          Tipo ID del declarante
  <IdInformante>...</IdInformante>                  RUC del declarante
  <razonSocial>...</razonSocial>
  <Anio>...</Anio>
  <Mes>...</Mes>
  <regimenMicroempresa>...</regimenMicroempresa>     SI/NO (semestral)
  <totalVentas>...</totalVentas>                    Suma bases imponibles ventas
  <codigoOperativo>IVA</codigoOperativo>

  <compras>
    <detalleCompras>
      <codSustento>01</codSustento>
      <tpIdProv>04</tpIdProv>
      <idProv>1234567890001</idProv>
      <tipoComprobante>01</tipoComprobante>
      <parteRel>NO</parteRel>
      <fechaRegistro>01/01/2025</fechaRegistro>
      <establecimiento>001</establecimiento>
      <puntoEmision>001</puntoEmision>
      <secuencial>000000001</secuencial>
      <fechaEmision>01/01/2025</fechaEmision>
      <autorizacion>...</autorizacion>
      <baseNoGraIva>0.00</baseNoGraIva>
      <baseImponible>0.00</baseImponible>
      <baseImpGrav>100.00</baseImpGrav>
      <baseImpExe>0.00</baseImpExe>
      <montoIce>0.00</montoIce>
      <montoIva>15.00</montoIva>
      <valRetBien10>0.00</valRetBien10>    (20% IVA bienes)
      <valRetServ20>0.00</valRetServ20>    (20% IVA servicios — NO EXISTE, es 30%)
      <valorRetBienes>0.00</valorRetBienes>
      <valorRetServicios>0.00</valorRetServicios>
      <valorRetServSinCostoBenef>0.00</valorRetServSinCostoBenef>
      <detalleAir>
        <codigo>307</codigo>
        <codigoRetencion>307</codigoRetencion>
        <baseImponible>100.00</baseImponible>
        <porcentajeRetener>1.00</porcentajeRetener>
        <valorRetenido>1.00</valorRetenido>
      </detalleAir>
      <estabRetencion1>001</estabRetencion1>
      <ptoEmiRetencion1>001</ptoEmiRetencion1>
      <secRetencion1>000000001</secRetencion1>
      <autRetencion1>...</autRetencion1>
      <fechaEmiRet1>01/01/2025</fechaEmiRet1>
      <formaPago>20</formaPago>
    </detalleCompras>
  </compras>

  <ventas>
    <detalleVentas>
      <tpIdCliente>04</tpIdCliente>
      <idCliente>1234567890001</idCliente>
      <parteRel>NO</parteRel>
      <tipoComprobante>01</tipoComprobante>
      <tipoEmision>F</tipoEmision>           F=física, E=electrónica
      <numeroComprobantes>1</numeroComprobantes>
      <baseNoGraIva>0.00</baseNoGraIva>
      <baseImponible>0.00</baseImponible>
      <baseImpGrav>100.00</baseImpGrav>
      <montoIva>15.00</montoIva>
      <montoIce>0.00</montoIce>
      <valorRetIva>0.00</valorRetIva>
      <valorRetRenta>0.00</valorRetRenta>
      <formaPago>20</formaPago>
    </detalleVentas>
  </ventas>
</iva>
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError

from odoo.addons.l10n_ec.models.res_partner import verify_final_consumer

from . import ec_ats_catalogos as CAT

import xml.etree.ElementTree as ET
from xml.dom import minidom
from collections import defaultdict
from datetime import datetime
import io
import logging
import re

_logger = logging.getLogger(__name__)


class EcAtsReport(models.AbstractModel):
    _name = 'ec.ats.report'
    _description = 'Generador ATS Ecuador'

    # ─────────────────────────────────────────────────────────────
    # MÉTODO PRINCIPAL — llamado desde el wizard
    # ─────────────────────────────────────────────────────────────

    @api.model
    def generate_ats(self, options):
        """
        Punto de entrada para generar el ATS completo.

        Args:
            options (dict): {
                'date_from': 'YYYY-MM-DD',
                'date_to': 'YYYY-MM-DD',
                'company_id': int,
                'include_electronic': bool,   # incluir docs electrónicos en módulo ventas
                'semestral': bool,
            }

        Returns:
            dict: {
                'xml': bytes,          # XML del ATS listo para DIMM
                'compras': list,       # datos de compras para vista/XLSX
                'ventas': list,        # datos de ventas para vista/XLSX
                'totales': dict,       # totales del período
            }
        """
        company = self.env['res.company'].browse(options.get('company_id', self.env.company.id))
        date_from = options['date_from']
        date_to = options['date_to']

        # Obtener movimientos del período
        compras = self._get_compras(company, date_from, date_to, options)
        ventas = self._get_ventas(company, date_from, date_to, options)
        exportaciones = self._get_exportaciones(company, date_from, date_to)
        anulados = self._get_anulados(company, date_from, date_to)
        ventas_establecimiento = self._get_ventas_establecimiento(ventas)

        # Calcular totales
        totales = self._calcular_totales(compras, ventas)

        # Generar XML
        xml_bytes = self._build_xml(
            company, date_from, date_to, options,
            compras, ventas, ventas_establecimiento, exportaciones, anulados, totales
        )

        return {
            'xml': xml_bytes,
            'compras': compras,
            'ventas': ventas,
            'ventas_establecimiento': ventas_establecimiento,
            'exportaciones': exportaciones,
            'anulados': anulados,
            'totales': totales,
        }

    # ─────────────────────────────────────────────────────────────
    # MÓDULO COMPRAS
    # ─────────────────────────────────────────────────────────────

    def _get_compras(self, company, date_from, date_to, options):
        """
        Extrae las facturas de proveedor del período y las transforma
        al formato requerido por el ATS (detalleCompras).

        Regla: los comprobantes de retención electrónicos NO se reportan
        en compras del ATS a partir de enero 2018 (ya los tiene el SRI).
        """
        domain = [
            ('company_id', '=', company.id),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
        ]

        moves = self.env['account.move'].search(domain, order='invoice_date, name')
        result = []

        for move in moves:
            proveedor = move.partner_id
            lineas_impuesto = self._get_tax_lines(move)

            # Determinar si aplica bancarización (forma de pago obligatoria)
            total_doc = abs(move.amount_total)
            fecha_doc = str(move.invoice_date)
            requiere_bancarizacion = self._requiere_bancarizacion(total_doc, fecha_doc)

            # Obtener retenciones emitidas para esta factura
            retenciones = self._get_retenciones_emitidas(move)

            registro = {
                # Identificación proveedor
                'codSustento': self._get_cod_sustento(move),
                'tpIdProv': self._get_tipo_id(proveedor, section='purchase'),
                'idProv': proveedor.vat or '',
                'tipoComprobante': self._get_tipo_comprobante(move),
                'parteRel': 'SI' if self._es_parte_relacionada(proveedor) else 'NO',

                # Datos del comprobante
                'fechaRegistro': self._format_date(move.date),
                'establecimiento': self._get_establecimiento(move.ref or move.name),
                'puntoEmision': self._get_punto_emision(move.ref or move.name),
                'secuencial': self._get_secuencial(move.ref or move.name),
                'fechaEmision': self._format_date(move.invoice_date),
                'autorizacion': self._get_autorizacion(move),

                # Bases imponibles
                'baseNoGraIva': lineas_impuesto.get('base_no_gra_iva', 0.0),
                'baseImponible': lineas_impuesto.get('base_0', 0.0),
                'baseImpGrav': lineas_impuesto.get('base_grav', 0.0),
                'baseImpExe': lineas_impuesto.get('base_exenta', 0.0),
                'montoIce': lineas_impuesto.get('ice', 0.0),
                'montoIva': lineas_impuesto.get('iva', 0.0),

                # Retenciones IVA (el declarante retiene al proveedor)
                'valRetBien10': retenciones.get('ret_iva_bienes_10', 0.0),
                'valRetServ20': retenciones.get('ret_iva_serv_20', 0.0),
                'valorRetBienes': retenciones.get('ret_iva_bienes', 0.0),
                'valRetServ50': retenciones.get('ret_iva_serv_50', 0.0),
                'valorRetServicios': retenciones.get('ret_iva_serv', 0.0),
                'valRetServ100': retenciones.get('ret_iva_sinCosto', 0.0),

                # Retenciones IR (detalleAir)
                'detalleAir': retenciones.get('detalleAir', []),

                # Datos del comprobante de retención emitido
                'estabRetencion1': retenciones.get('estab_ret', ''),
                'ptoEmiRetencion1': retenciones.get('pto_ret', ''),
                'secRetencion1': retenciones.get('sec_ret', ''),
                'autRetencion1': retenciones.get('aut_ret', ''),
                'fechaEmiRet1': retenciones.get('fecha_ret', ''),

                # Forma de pago
                'formaPago': self._get_forma_pago(move) if requiere_bancarizacion else '',

                # Metadatos (para vista en pantalla y XLSX)
                '_move_id': move.id,
                '_proveedor_nombre': proveedor.name,
                '_numero': move.name,
                '_total': abs(move.amount_total),
                '_tipo': move.move_type,
            }
            result.append(registro)

        return result

    # ─────────────────────────────────────────────────────────────
    # MÓDULO VENTAS
    # ─────────────────────────────────────────────────────────────

    def _get_ventas(self, company, date_from, date_to, options):
        """
        Extrae las facturas de cliente del período.

        El ATS de ventas agrupa por:
        - Tipo de identificación del cliente
        - Tipo de comprobante
        - Tipo de emisión (F=física, E=electrónica)

        REGLA IMPORTANTE (desde 2015):
        Los documentos electrónicos (facturas, NC, ND) NO deben reportarse
        en el módulo de ventas si cumplen los formatos vigentes del SRI
        (el SRI ya los tiene por el proceso de autorización).
        Esta regla se respeta según la opción 'include_electronic'.
        """
        domain = [
            ('company_id', '=', company.id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
        ]

        # Filtrar electrónicos si la opción está activa
        include_electronic = options.get('include_electronic', False)
        if not include_electronic:
            # Excluir facturas electrónicas autorizadas por SRI.
            # El nombre del campo cambia según localización instalada.
            auth_field = self._get_electronic_authorization_field()
            if auth_field:
                domain.append((auth_field, '=', False))
            else:
                _logger.warning(
                    "ATS: no se encontró campo de autorización electrónica en account.move; "
                    "se incluirán documentos electrónicos en ventas."
                )

        moves = self.env['account.move'].search(domain, order='partner_id, move_type')

        # El ATS agrupa ventas por: tpIdCliente + tipoComprobante + tipoEmision
        grupos = defaultdict(lambda: {
            'tpIdCliente': '',
            'idCliente': '',
            'parteRel': 'NO',
            'tipoComprobante': '',
            'tipoEmision': 'F',
            'numeroComprobantes': 0,
            'baseNoGraIva': 0.0,
            'baseImponible': 0.0,
            'baseImpGrav': 0.0,
            'montoIva': 0.0,
            'montoIce': 0.0,
            'valorRetIva': 0.0,
            'valorRetRenta': 0.0,
            'formaPago': '20',
            '_clientes': [],
        })

        result = []
        for move in moves:
            cliente = move.partner_id
            lineas = self._get_tax_lines(move)
            tipo_id = self._get_tipo_id(cliente, section='sale')
            tipo_comp = self._get_tipo_comprobante(move)
            es_electronica = bool(self._get_autorizacion(move))
            tipo_emision = 'E' if es_electronica else 'F'

            # Obtener retenciones que el cliente realizó a la empresa
            ret_recibidas = self._get_retenciones_recibidas(move)

            total_doc = abs(move.amount_total)
            fecha_doc = str(move.invoice_date)
            requiere_bancarizacion = self._requiere_bancarizacion(total_doc, fecha_doc)

            registro = {
                'tpIdCliente': tipo_id,
                'idCliente': cliente.vat or '9999999999999' if tipo_id == '07' else (cliente.vat or ''),
                'parteRel': 'SI' if self._es_parte_relacionada(cliente) else 'NO',
                'tipoComprobante': tipo_comp,
                'tipoEmision': tipo_emision,
                'numeroComprobantes': 1,
                'baseNoGraIva': lineas.get('base_no_gra_iva', 0.0),
                'baseImponible': lineas.get('base_0', 0.0),
                'baseImpGrav': lineas.get('base_grav', 0.0),
                'montoIva': lineas.get('iva', 0.0),
                'montoIce': lineas.get('ice', 0.0),
                'valorRetIva': ret_recibidas.get('iva', 0.0),
                'valorRetRenta': ret_recibidas.get('ir', 0.0),
                'formaPago': self._get_forma_pago_cobro(move) if requiere_bancarizacion else '',
                'codEstab': self._get_cod_estab_move(move),

                # Metadatos para vista y XLSX
                '_move_id': move.id,
                '_cliente_nombre': cliente.name,
                '_numero': move.name,
                '_total': abs(move.amount_total),
                '_tipo': move.move_type,
                '_fecha': str(move.invoice_date),
            }
            result.append(registro)

        return result

    def _get_ventas_establecimiento(self, ventas):
        """
        Consolida ventas por establecimiento para el bloque ventasEstablecimiento.
        Regla: usa l10n_ec_entity del diario cuando existe; fallback al número del documento.
        """
        totales_estab = defaultdict(float)
        for venta in ventas:
            cod_estab = str(venta.get('codEstab') or '').zfill(3)
            if not cod_estab.isdigit():
                cod_estab = '001'
            monto = (
                float(venta.get('baseNoGraIva', 0.0) or 0.0)
                + float(venta.get('baseImponible', 0.0) or 0.0)
                + float(venta.get('baseImpGrav', 0.0) or 0.0)
            )
            totales_estab[cod_estab] += monto

        return [
            {
                'codEstab': estab,
                'ventasEstab': total,
                'ivaComp': 0.0,
            }
            for estab, total in sorted(totales_estab.items())
        ]

    # ─────────────────────────────────────────────────────────────
    # MÓDULO EXPORTACIONES
    # ─────────────────────────────────────────────────────────────

    def _get_exportaciones(self, company, date_from, date_to):
        """Extrae documentos de exportación (tipoComprobante = '10')."""
        domain = [
            ('company_id', '=', company.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', date_from),
            ('invoice_date', '<=', date_to),
            # Exportaciones se identifican por el diario o por un campo específico
            # En l10n_ec_edi se puede usar el tipo de documento de la factura
            ('journal_id.l10n_ec_emission_type', '=', 'exportation'),
        ]

        try:
            moves = self.env['account.move'].search(domain)
        except Exception:
            # Si el campo no existe (versión sin l10n_ec_edi), retornar vacío
            return []

        result = []
        for move in moves:
            result.append({
                'tpIdClienteEx': self._get_tipo_id(move.partner_id, section='export') or '20',
                'idClienteEx': move.partner_id.vat or '',
                'parteRelExp': 'SI' if self._es_parte_relacionada(move.partner_id) else 'NO',
                'exportacionDe': '01',
                'tipoComprobante': '10',
                'fechaEmbarque': self._format_date(move.invoice_date),
                'valorFOB': abs(move.amount_untaxed),
                'valorFOBComprobante': abs(move.amount_untaxed),
                'establecimiento': self._get_establecimiento(move.name),
                'puntoEmision': self._get_punto_emision(move.name),
                'secuencial': self._get_secuencial(move.name),
                'autorizacion': self._sanitize_authorization(self._get_autorizacion(move)),
                'fechaEmision': self._format_date(move.invoice_date),
                '_move_id': move.id,
                '_cliente_nombre': move.partner_id.name,
                '_numero': move.name,
                '_total': abs(move.amount_total),
            })
        return result

    # ─────────────────────────────────────────────────────────────
    # MÓDULO ANULADOS
    # ─────────────────────────────────────────────────────────────

    def _get_anulados(self, company, date_from, date_to):
        """
        Extrae comprobantes anulados (estado cancelled) del período.
        Solo aplica para documentos físicos (preimpresos).
        """
        domain = [
            ('company_id', '=', company.id),
            ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
            ('state', '=', 'cancel'),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ]

        moves = self.env['account.move'].search(domain)
        result = []
        for move in moves:
            result.append({
                'tipoComprobante': self._get_tipo_comprobante(move),
                'establecimiento': self._get_establecimiento(move.name),
                'puntoEmision': self._get_punto_emision(move.name),
                'secuencialInicio': self._get_secuencial(move.name),
                'secuencialFin': self._get_secuencial(move.name),
                '_numero': move.name,
                '_tipo': move.move_type,
            })
        return result

    # ─────────────────────────────────────────────────────────────
    # CONSTRUCCIÓN DEL XML
    # ─────────────────────────────────────────────────────────────

    def _build_xml(self, company, date_from, date_to, options,
                   compras, ventas, ventas_establecimiento, exportaciones, anulados, totales):
        """
        Construye el XML del ATS conforme al esquema at.xsd del SRI.

        Encoding: UTF-8
        Namespace: ninguno (el at.xsd no usa namespace)
        """
        mes = date_from[5:7]
        anio = self._to_plain_year(date_from[:4])
        es_semestral = options.get('semestral', False)

        # Nodo raíz
        root = ET.Element('iva')

        # ── CABECERA ──
        ET.SubElement(root, 'TipoIDInformante').text = 'R'
        ET.SubElement(root, 'IdInformante').text = self._sanitize_ruc(company.vat)
        ET.SubElement(root, 'razonSocial').text = self._sanitize_razon_social(company.name)
        ET.SubElement(root, 'Anio').text = anio
        ET.SubElement(root, 'Mes').text = mes
        ET.SubElement(root, 'numEstabRuc').text = self._get_num_estab(company)
        ET.SubElement(root, 'totalVentas').text = self._fmt_total(totales.get('total_ventas_base', 0.0))
        ET.SubElement(root, 'codigoOperativo').text = 'IVA'

        if es_semestral:
            ET.SubElement(root, 'regimenMicroempresa').text = 'SI'

        # ── MÓDULO COMPRAS ──
        if compras:
            nodo_compras = ET.SubElement(root, 'compras')
            for c in compras:
                self._build_detalle_compra(nodo_compras, c)

        # ── MÓDULO VENTAS ──
        if ventas:
            nodo_ventas = ET.SubElement(root, 'ventas')
            for v in ventas:
                self._build_detalle_venta(nodo_ventas, v)

        # ── MÓDULO VENTAS POR ESTABLECIMIENTO ──
        if ventas_establecimiento:
            nodo_ventas_estab = ET.SubElement(root, 'ventasEstablecimiento')
            for v_est in ventas_establecimiento:
                self._build_venta_establecimiento(nodo_ventas_estab, v_est)

        # ── MÓDULO EXPORTACIONES ──
        if exportaciones:
            nodo_exp = ET.SubElement(root, 'exportaciones')
            for e in exportaciones:
                self._build_detalle_exportacion(nodo_exp, e)

        # ── MÓDULO ANULADOS ──
        if anulados:
            nodo_anu = ET.SubElement(root, 'anulados')
            for a in anulados:
                self._build_detalle_anulado(nodo_anu, a)

        # Serializar
        raw = ET.tostring(root, encoding='unicode')
        parsed = minidom.parseString(f'<?xml version="1.0" encoding="UTF-8"?>{raw}')
        return parsed.toprettyxml(indent='  ', encoding='UTF-8')

    def _build_detalle_compra(self, parent, c):
        dc = ET.SubElement(parent, 'detalleCompras')

        ET.SubElement(dc, 'codSustento').text = c.get('codSustento', '01')
        ET.SubElement(dc, 'tpIdProv').text = c.get('tpIdProv', '04')
        ET.SubElement(dc, 'idProv').text = self._sanitize_identifier(c.get('idProv', ''), fallback='000')
        ET.SubElement(dc, 'tipoComprobante').text = c.get('tipoComprobante', '01')
        ET.SubElement(dc, 'parteRel').text = c.get('parteRel', 'NO')
        ET.SubElement(dc, 'fechaRegistro').text = c.get('fechaRegistro', '')
        ET.SubElement(dc, 'establecimiento').text = c.get('establecimiento', '001')
        ET.SubElement(dc, 'puntoEmision').text = c.get('puntoEmision', '001')
        ET.SubElement(dc, 'secuencial').text = c.get('secuencial', '000000001')
        ET.SubElement(dc, 'fechaEmision').text = c.get('fechaEmision', '')
        ET.SubElement(dc, 'autorizacion').text = self._sanitize_authorization(c.get('autorizacion', ''))
        ET.SubElement(dc, 'baseNoGraIva').text = self._fmt(c.get('baseNoGraIva', 0.0))
        ET.SubElement(dc, 'baseImponible').text = self._fmt(c.get('baseImponible', 0.0))
        ET.SubElement(dc, 'baseImpGrav').text = self._fmt(c.get('baseImpGrav', 0.0))
        ET.SubElement(dc, 'baseImpExe').text = self._fmt(c.get('baseImpExe', 0.0))
        ET.SubElement(dc, 'montoIce').text = self._fmt(c.get('montoIce', 0.0))
        ET.SubElement(dc, 'montoIva').text = self._fmt(c.get('montoIva', 0.0))
        ET.SubElement(dc, 'valRetBien10').text = self._fmt(c.get('valRetBien10', 0.0))
        ET.SubElement(dc, 'valRetServ20').text = self._fmt(c.get('valRetServ20', 0.0))
        ET.SubElement(dc, 'valorRetBienes').text = self._fmt(c.get('valorRetBienes', 0.0))
        ET.SubElement(dc, 'valRetServ50').text = self._fmt(c.get('valRetServ50', 0.0))
        ET.SubElement(dc, 'valorRetServicios').text = self._fmt(c.get('valorRetServicios', 0.0))
        ET.SubElement(dc, 'valRetServ100').text = self._fmt(c.get('valRetServ100', 0.0))

        # Retenciones IR — puede haber múltiples conceptos por factura
        detalle_air = c.get('detalleAir', [])
        if detalle_air:
            nodo_air_parent = ET.SubElement(dc, 'air')
            for air in detalle_air:
                nodo_air = ET.SubElement(nodo_air_parent, 'detalleAir')
                ET.SubElement(nodo_air, 'codRetAir').text = str(
                    air.get('codigoRetencion') or air.get('codigo') or ''
                )
                ET.SubElement(nodo_air, 'baseImpAir').text = self._fmt(air.get('baseImponible', 0.0))
                ET.SubElement(nodo_air, 'porcentajeAir').text = self._fmt(air.get('porcentajeRetener', 0.0))
                ET.SubElement(nodo_air, 'valRetAir').text = self._fmt(air.get('valorRetenido', 0.0))

        # Datos del comprobante de retención (si se emitió)
        if c.get('estabRetencion1'):
            ET.SubElement(dc, 'estabRetencion1').text = c.get('estabRetencion1', '')
            ET.SubElement(dc, 'ptoEmiRetencion1').text = c.get('ptoEmiRetencion1', '')
            ET.SubElement(dc, 'secRetencion1').text = c.get('secRetencion1', '')
            ET.SubElement(dc, 'autRetencion1').text = self._sanitize_authorization(c.get('autRetencion1', ''))
            ET.SubElement(dc, 'fechaEmiRet1').text = c.get('fechaEmiRet1', '')

        if c.get('formaPago'):
            formas_pago = ET.SubElement(dc, 'formasDePago')
            for forma in self._split_formas_pago(c.get('formaPago', '')):
                ET.SubElement(formas_pago, 'formaPago').text = forma

    def _build_detalle_venta(self, parent, v):
        dv = ET.SubElement(parent, 'detalleVentas')

        ET.SubElement(dv, 'tpIdCliente').text = v.get('tpIdCliente', '04')
        ET.SubElement(dv, 'idCliente').text = self._sanitize_identifier(v.get('idCliente', ''), fallback='000')
        ET.SubElement(dv, 'parteRelVtas').text = v.get('parteRel', 'NO')
        ET.SubElement(dv, 'tipoComprobante').text = v.get('tipoComprobante', '01')
        ET.SubElement(dv, 'tipoEmision').text = v.get('tipoEmision', 'F')
        ET.SubElement(dv, 'numeroComprobantes').text = str(v.get('numeroComprobantes', 1))
        ET.SubElement(dv, 'baseNoGraIva').text = self._fmt(v.get('baseNoGraIva', 0.0))
        ET.SubElement(dv, 'baseImponible').text = self._fmt(v.get('baseImponible', 0.0))
        ET.SubElement(dv, 'baseImpGrav').text = self._fmt(v.get('baseImpGrav', 0.0))
        ET.SubElement(dv, 'montoIva').text = self._fmt(v.get('montoIva', 0.0))
        ET.SubElement(dv, 'montoIce').text = self._fmt(v.get('montoIce', 0.0))
        ET.SubElement(dv, 'valorRetIva').text = self._fmt(v.get('valorRetIva', 0.0))
        ET.SubElement(dv, 'valorRetRenta').text = self._fmt(v.get('valorRetRenta', 0.0))

        if v.get('formaPago'):
            formas_pago = ET.SubElement(dv, 'formasDePago')
            for forma in self._split_formas_pago(v.get('formaPago', '')):
                ET.SubElement(formas_pago, 'formaPago').text = forma

    def _build_detalle_exportacion(self, parent, e):
        de = ET.SubElement(parent, 'detalleExportaciones')
        ET.SubElement(de, 'tpIdClienteEx').text = e.get('tpIdClienteEx', '20')
        ET.SubElement(de, 'idClienteEx').text = self._sanitize_identifier(e.get('idClienteEx', ''), fallback='000')
        ET.SubElement(de, 'parteRelExp').text = e.get('parteRelExp', 'NO')
        ET.SubElement(de, 'exportacionDe').text = e.get('exportacionDe', '01')
        ET.SubElement(de, 'tipoComprobante').text = '10'
        ET.SubElement(de, 'fechaEmbarque').text = e.get('fechaEmbarque', '')
        ET.SubElement(de, 'valorFOB').text = self._fmt(e.get('valorFOB', 0.0))
        ET.SubElement(de, 'valorFOBComprobante').text = self._fmt(e.get('valorFOBComprobante', 0.0))
        ET.SubElement(de, 'establecimiento').text = e.get('establecimiento', '001')
        ET.SubElement(de, 'puntoEmision').text = e.get('puntoEmision', '001')
        ET.SubElement(de, 'secuencial').text = e.get('secuencial', '000000001')
        ET.SubElement(de, 'autorizacion').text = self._sanitize_authorization(e.get('autorizacion', ''))
        ET.SubElement(de, 'fechaEmision').text = e.get('fechaEmision', '')

    def _build_venta_establecimiento(self, parent, venta_est):
        ve = ET.SubElement(parent, 'ventaEst')
        ET.SubElement(ve, 'codEstab').text = str(venta_est.get('codEstab', '001')).zfill(3)
        ET.SubElement(ve, 'ventasEstab').text = self._fmt_total(venta_est.get('ventasEstab', 0.0))
        ET.SubElement(ve, 'ivaComp').text = self._fmt_total(venta_est.get('ivaComp', 0.0))

    def _build_detalle_anulado(self, parent, a):
        da = ET.SubElement(parent, 'detalleAnulados')
        ET.SubElement(da, 'tipoComprobante').text = a.get('tipoComprobante', '01')
        ET.SubElement(da, 'establecimiento').text = a.get('establecimiento', '001')
        ET.SubElement(da, 'puntoEmision').text = a.get('puntoEmision', '001')
        ET.SubElement(da, 'secuencialInicio').text = a.get('secuencialInicio', '000000001')
        ET.SubElement(da, 'secuencialFin').text = a.get('secuencialFin', '000000001')
        ET.SubElement(da, 'autorizacion').text = self._sanitize_authorization(a.get('autorizacion', ''))

    # ─────────────────────────────────────────────────────────────
    # GENERACIÓN XLSX
    # ─────────────────────────────────────────────────────────────

    def generate_xlsx(self, ats_data):
        """
        Genera el XLSX del ATS con hojas separadas por sección.
        """
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_('Por favor instale xlsxwriter: pip install xlsxwriter'))

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})

        # Formatos
        fmt_title = wb.add_format({'bold': True, 'font_size': 12, 'bg_color': '#1F4E79',
                                   'font_color': '#FFFFFF', 'align': 'center'})
        fmt_header = wb.add_format({'bold': True, 'bg_color': '#2E75B6', 'font_color': '#FFFFFF',
                                    'border': 1, 'text_wrap': True, 'font_size': 9})
        fmt_data = wb.add_format({'border': 1, 'font_size': 9})
        fmt_num = wb.add_format({'border': 1, 'font_size': 9, 'num_format': '#,##0.00'})
        fmt_total = wb.add_format({'bold': True, 'border': 1, 'num_format': '#,##0.00',
                                   'bg_color': '#FFF2CC'})

        # Hoja COMPRAS
        ws_c = wb.add_worksheet('COMPRAS')
        ws_c.freeze_panes(2, 0)
        c_headers = [
            'Cod.Sustento', 'Tp.ID Prov', 'ID Proveedor', 'Nombre Proveedor',
            'Tp.Comprobante', 'Parte Rel', 'F.Registro', 'Estab', 'Pto.Emi',
            'Secuencial', 'F.Emisión', 'Autorización',
            'Base No Gra.IVA', 'Base Imp.0%', 'Base Imp.Grav', 'Base Exenta',
            'ICE', 'IVA', 'Ret.IVA Bienes', 'Ret.IVA Serv', 'Forma Pago'
        ]
        col_w = [12, 8, 16, 30, 12, 9, 11, 6, 6, 12, 11, 20, 14, 14, 14, 14, 10, 10, 14, 14, 12]
        ws_c.merge_range(0, 0, 0, len(c_headers)-1, 'ATS - MÓDULO COMPRAS', fmt_title)
        for i, h in enumerate(c_headers):
            ws_c.write(1, i, h, fmt_header)
            ws_c.set_column(i, i, col_w[i])

        num_fields = {'baseNoGraIva', 'baseImponible', 'baseImpGrav', 'baseImpExe',
                      'montoIce', 'montoIva', 'valorRetBienes', 'valorRetServicios'}
        for row_i, c in enumerate(ats_data.get('compras', []), start=2):
            vals = [
                c.get('codSustento', ''), c.get('tpIdProv', ''), c.get('idProv', ''),
                c.get('_proveedor_nombre', ''), c.get('tipoComprobante', ''),
                c.get('parteRel', 'NO'), c.get('fechaRegistro', ''),
                c.get('establecimiento', ''), c.get('puntoEmision', ''),
                c.get('secuencial', ''), c.get('fechaEmision', ''), c.get('autorizacion', ''),
                c.get('baseNoGraIva', 0.0), c.get('baseImponible', 0.0),
                c.get('baseImpGrav', 0.0), c.get('baseImpExe', 0.0),
                c.get('montoIce', 0.0), c.get('montoIva', 0.0),
                c.get('valorRetBienes', 0.0), c.get('valorRetServicios', 0.0),
                c.get('formaPago', ''),
            ]
            for col_i, val in enumerate(vals):
                fmt = fmt_num if isinstance(val, float) else fmt_data
                ws_c.write(row_i, col_i, val, fmt)

        # Hoja VENTAS
        ws_v = wb.add_worksheet('VENTAS')
        ws_v.freeze_panes(2, 0)
        v_headers = [
            'Tp.ID Cliente', 'ID Cliente', 'Nombre Cliente', 'Parte Rel',
            'Tp.Comprobante', 'Tp.Emisión', 'Nro.Comprobantes',
            'Base No Gra.IVA', 'Base Imp.0%', 'Base Imp.Grav',
            'IVA', 'ICE', 'Ret.IVA', 'Ret.Renta', 'Forma Cobro',
            'Número Doc', 'Fecha', 'Total'
        ]
        ws_v.merge_range(0, 0, 0, len(v_headers)-1, 'ATS - MÓDULO VENTAS', fmt_title)
        for i, h in enumerate(v_headers):
            ws_v.write(1, i, h, fmt_header)
        for row_i, v in enumerate(ats_data.get('ventas', []), start=2):
            vals = [
                v.get('tpIdCliente', ''), v.get('idCliente', ''), v.get('_cliente_nombre', ''),
                v.get('parteRel', 'NO'), v.get('tipoComprobante', ''), v.get('tipoEmision', 'F'),
                v.get('numeroComprobantes', 1),
                v.get('baseNoGraIva', 0.0), v.get('baseImponible', 0.0), v.get('baseImpGrav', 0.0),
                v.get('montoIva', 0.0), v.get('montoIce', 0.0),
                v.get('valorRetIva', 0.0), v.get('valorRetRenta', 0.0), v.get('formaPago', ''),
                v.get('_numero', ''), v.get('_fecha', ''), v.get('_total', 0.0),
            ]
            for col_i, val in enumerate(vals):
                fmt = fmt_num if isinstance(val, float) else fmt_data
                ws_v.write(row_i, col_i, val, fmt)

        # Hoja TOTALES
        ws_t = wb.add_worksheet('TOTALES')
        ws_t.set_column('A:B', 30)
        ws_t.merge_range(0, 0, 0, 1, 'ATS - TOTALES DEL PERÍODO', fmt_title)
        totales = ats_data.get('totales', {})
        filas_tot = [
            ('Total ventas (bases)', totales.get('total_ventas_base', 0.0)),
            ('Total IVA cobrado', totales.get('total_iva_ventas', 0.0)),
            ('Total compras (bases)', totales.get('total_compras_base', 0.0)),
            ('Total IVA en compras', totales.get('total_iva_compras', 0.0)),
            ('Total retenciones IVA emitidas', totales.get('total_ret_iva', 0.0)),
            ('Total retenciones IR emitidas', totales.get('total_ret_ir', 0.0)),
            ('Documentos de compra', totales.get('num_compras', 0)),
            ('Documentos de venta', totales.get('num_ventas', 0)),
        ]
        for row_i, (label, val) in enumerate(filas_tot, start=2):
            ws_t.write(row_i, 0, label, fmt_data)
            fmt = fmt_total if isinstance(val, float) else fmt_data
            ws_t.write(row_i, 1, val, fmt)

        wb.close()
        return output.getvalue()

    # ─────────────────────────────────────────────────────────────
    # MÉTODOS AUXILIARES
    # ─────────────────────────────────────────────────────────────

    def _get_tax_lines(self, move):
        """
        Desglosa las líneas de impuesto de un move en las categorías
        requeridas por el ATS:
          - base_grav: base imponible con IVA (15%)
          - base_0: base imponible tarifa 0%
          - base_no_gra_iva: no objeto de IVA
          - base_exenta: exenta de IVA
          - iva: monto de IVA
          - ice: monto de ICE
        """
        result = {
            'base_grav': 0.0,
            'base_0': 0.0,
            'base_no_gra_iva': 0.0,
            'base_exenta': 0.0,
            'iva': 0.0,
            'ice': 0.0,
        }
        sign = 1 if move.move_type in ('out_invoice', 'in_invoice') else -1

        for line in move.line_ids:
            if line.display_type != 'tax':
                continue
            for tax in line.tax_ids:
                tax_name = (tax.name or '').lower()
                if 'iva' in tax_name or 'igv' in tax_name:
                    if tax.amount > 0:
                        result['iva'] += abs(line.balance) * sign
                    elif tax.amount == 0:
                        # IVA 0%: la base está en las líneas de producto
                        pass
                elif 'ice' in tax_name:
                    result['ice'] += abs(line.balance) * sign

        # Calcular bases desde las líneas de producto
        for line in move.line_ids:
            if line.display_type != 'product':
                continue
            taxes = line.tax_ids
            tax_names = [(t.name or '').lower() for t in taxes]
            has_iva_grav = any('iva' in n and t.amount > 0 for n, t in zip(tax_names, taxes))
            has_iva_0 = any('iva' in n and t.amount == 0 for n, t in zip(tax_names, taxes))
            has_no_iva = not any('iva' in n for n in tax_names)

            base = abs(line.price_subtotal) * sign
            if has_iva_grav:
                result['base_grav'] += base
            elif has_iva_0:
                result['base_0'] += base
            elif has_no_iva:
                # Distinguir entre "no objeto" y "exenta" requiere configuración adicional
                result['base_no_gra_iva'] += base

        return result

    def _get_retenciones_emitidas(self, move):
        """
        Busca los comprobantes de retención emitidos por la empresa
        para la factura de proveedor dada.
        Retorna los valores desglosados para el XML del ATS.
        """
        result = {
            'ret_iva_bienes_10': 0.0,
            'ret_iva_serv_20': 0.0,
            'ret_iva_bienes': 0.0,
            'ret_iva_serv_50': 0.0,
            'ret_iva_serv': 0.0,
            'ret_iva_sinCosto': 0.0,
            'detalleAir': [],
            'estab_ret': '',
            'pto_ret': '',
            'sec_ret': '',
            'aut_ret': '',
            'fecha_ret': '',
        }

        # Buscar retenciones relacionadas a este move
        # En l10n_ec_withhold de OCA, las retenciones se almacenan en
        # account.move con tipo 'entry' y linked al move original
        retencion_moves = self.env['account.move'].search([
            ('ref', '=', move.name),
            ('move_type', '=', 'entry'),
            ('state', '=', 'posted'),
            ('company_id', '=', move.company_id.id),
        ])

        # Alternativamente, buscar por el campo específico de OCA
        if hasattr(move, 'l10n_ec_withhold_ids'):
            retencion_moves = move.l10n_ec_withhold_ids.filtered(lambda r: r.state == 'posted')

        for ret_move in retencion_moves:
            # Parsear número del comprobante de retención
            ret_num = ret_move.name or ''
            result['estab_ret'] = self._get_establecimiento(ret_num)
            result['pto_ret'] = self._get_punto_emision(ret_num)
            result['sec_ret'] = self._get_secuencial(ret_num)
            result['aut_ret'] = self._get_autorizacion(ret_move)
            result['fecha_ret'] = self._format_date(ret_move.date)

            # Analizar líneas de retención
            for line in ret_move.line_ids:
                for tax in line.tax_ids:
                    tax_name = (tax.name or '').upper()
                    val = abs(line.balance)

                    if 'IVA' in tax_name:
                        pct = abs(tax.amount)
                        if pct == 10:
                            result['ret_iva_bienes_10'] += val
                        elif pct == 20:
                            result['ret_iva_serv_20'] += val
                        elif pct == 30:
                            result['ret_iva_bienes'] += val
                        elif pct == 50:
                            result['ret_iva_serv_50'] += val
                        elif pct == 70:
                            result['ret_iva_serv'] += val
                        elif pct == 100:
                            result['ret_iva_sinCosto'] += val
                        elif pct < 30:
                            result['ret_iva_serv_20'] += val
                        elif pct < 50:
                            result['ret_iva_bienes'] += val
                        elif pct < 70:
                            result['ret_iva_serv_50'] += val
                        elif pct < 100:
                            result['ret_iva_serv'] += val
                        else:
                            result['ret_iva_sinCosto'] += val

                    elif 'IR' in tax_name or 'RENTA' in tax_name:
                        # Determinar código concepto de retención IR
                        cod = self._get_codigo_ret_ir(tax)
                        if cod:
                            result['detalleAir'].append({
                                'codigo': cod,
                                'codigoRetencion': cod,
                                'baseImponible': abs(line.price_subtotal or line.balance / (tax.amount / 100)),
                                'porcentajeRetener': abs(tax.amount),
                                'valorRetenido': val,
                            })

        return result

    def _get_retenciones_recibidas(self, move):
        """
        Busca retenciones que el cliente realizó a la empresa (en facturas de venta).
        Estas se reportan en el módulo de ventas del ATS.
        """
        result = {'iva': 0.0, 'ir': 0.0}
        if hasattr(move, 'l10n_ec_withhold_received_ids'):
            for ret in move.l10n_ec_withhold_received_ids.filtered(lambda r: r.state == 'posted'):
                for line in ret.line_ids:
                    for tax in line.tax_ids:
                        if 'IVA' in (tax.name or '').upper():
                            result['iva'] += abs(line.balance)
                        else:
                            result['ir'] += abs(line.balance)
        return result

    def _get_tipo_id(self, partner, section='sale'):
        """
        Determina el codigo ATS de tipo de identificacion (Tabla 1 del at.xsd).
        Usa el tipo de identificacion LATAM que gestiona la localizacion
        ecuatoriana (l10n_ec / l10n_ec_base) mediante
        res.partner._l10n_ec_get_identification_type(), con fallback por VAT.
        """
        section = (section or 'sale').strip().lower()
        if not partner:
            return '07' if section == 'sale' else ('21' if section == 'export' else '03')

        vat = partner.vat or ''

        # Consumidor final (9999999999999) se reporta con codigo 07 en ventas.
        if section == 'sale' and verify_final_consumer(vat):
            return '07'

        if partner.l10n_latam_identification_type_id and hasattr(
            partner, '_l10n_ec_get_identification_type'
        ):
            partner_type = partner._l10n_ec_get_identification_type()
            if section == 'purchase':
                if partner_type == 'ruc':
                    return '01'
                if partner_type == 'cedula':
                    return '02'
                return '03'
            if section == 'export':
                if partner_type == 'ruc':
                    return '20'
                return '21'
            # section == 'sale'
            if partner_type == 'ruc':
                return '04'
            if partner_type == 'cedula':
                return '05'
            return '06'

        # Fallback defensivo para partners sin tipo de identificacion configurado.
        if section == 'purchase':
            if len(vat) == 13:
                return '01'
            if len(vat) == 10:
                return '02'
            return '03'
        if section == 'export':
            if len(vat) == 13:
                return '20'
            return '21'
        if len(vat) == 13:
            return '04'
        if len(vat) == 10:
            return '05'
        return '06'

    def _get_tipo_comprobante(self, move):
        """Determina el código de tipo de comprobante (Tabla 2)."""
        # Intentar obtener del campo de l10n_ec_edi
        if hasattr(move, 'l10n_ec_document_type'):
            dt = getattr(move, 'l10n_ec_document_type', None)
            if dt:
                return str(dt).zfill(2)

        # Fallback por tipo de movimiento
        mapping = {
            'out_invoice': '01',
            'out_refund': '04',
            'in_invoice': '01',
            'in_refund': '04',
        }
        return mapping.get(move.move_type, '01')

    def _get_cod_sustento(self, move):
        """
        Determina el código de sustento tributario (Tabla 9).
        Se puede configurar por línea de factura o usar el de la localización OCA.
        """
        # OCA l10n_ec puede tener el campo en account.move
        if hasattr(move, 'l10n_ec_tax_support'):
            val = getattr(move, 'l10n_ec_tax_support', None)
            if val:
                return str(val).zfill(2)
        # Default: 01 = Crédito tributario IVA
        return '01'

    def _get_establecimiento(self, ref):
        """Extrae establecimiento desde el número de comprobante con fallback seguro."""
        estab, _pto, _sec = self._extract_comprobante_parts(ref)
        return estab

    def _get_punto_emision(self, ref):
        _estab, pto, _sec = self._extract_comprobante_parts(ref)
        return pto

    def _get_secuencial(self, ref):
        _estab, _pto, sec = self._extract_comprobante_parts(ref)
        return sec

    def _extract_comprobante_parts(self, ref):
        """
        Extrae (estab, pto_emi, secuencial) buscando un patrón numérico robusto.
        Acepta separadores no estándar y evita propagar prefijos alfanuméricos.
        """
        text = str(ref or '').strip()
        if not text:
            return '001', '001', '000000001'

        match = re.search(r'(\d{3})\D+(\d{3})\D+(\d{1,9})(?!\d)', text)
        if match:
            estab, pto, sec = match.groups()
            return estab.zfill(3), pto.zfill(3), sec.zfill(9)

        # Fallback: usar grupos de dígitos en orden (si existen).
        groups = re.findall(r'\d+', text)
        if len(groups) >= 3:
            estab = groups[0][-3:].zfill(3)
            pto = groups[1][-3:].zfill(3)
            sec = groups[2][-9:].zfill(9)
            return estab, pto, sec

        return '001', '001', '000000001'

    def _get_autorizacion(self, move):
        """Obtiene el número de autorización del comprobante."""
        for field_name in (
            'l10n_ec_authorization',
            'l10n_ec_electronic_authorization',
            'l10n_ec_legacy_document_authorization',
            'l10n_ec_xml_access_key',
        ):
            if field_name in move._fields:
                value = getattr(move, field_name, False)
                if value:
                    return value
        return ''

    def _get_electronic_authorization_field(self):
        """
        Devuelve el campo que identifica autorización electrónica en account.move.
        Compatible con localización oficial y OCA.
        """
        move_fields = self.env['account.move']._fields
        for field_name in ('l10n_ec_authorization', 'l10n_ec_electronic_authorization'):
            if field_name in move_fields:
                return field_name
        return False

    def _get_forma_pago(self, move):
        """Obtiene la forma de pago de una factura de compra."""
        # OCA puede tener campo de forma de pago
        if hasattr(move, 'l10n_ec_payment_method'):
            val = getattr(move, 'l10n_ec_payment_method', None)
            if val:
                return str(val).zfill(2)
        # Si pagó con tarjeta de crédito del sistema financiero
        if move.amount_total >= CAT.LIMITE_BANCARIZACION_DESDE_DIC2023:
            return '20'  # Otros con sistema financiero (por defecto)
        return '01'  # Sin sistema financiero

    def _get_forma_pago_cobro(self, move):
        """Obtiene la forma de cobro de una factura de venta."""
        return self._get_forma_pago(move)

    def _get_cod_estab_move(self, move):
        """
        Obtiene código de establecimiento para ATS:
        - Preferente: l10n_ec_entity del diario si usa documentos latam.
        - Fallback: establecimiento del número del documento.
        """
        journal = move.journal_id
        if journal and getattr(journal, 'l10n_latam_use_documents', False):
            entity = str(getattr(journal, 'l10n_ec_entity', '') or '').strip()
            if entity.isdigit():
                return entity.zfill(3)
        return self._get_establecimiento(move.ref or move.name)

    def _es_parte_relacionada(self, partner):
        """Detecta si el partner es parte relacionada."""
        return getattr(partner, 'l10n_ec_related_party', False)

    def _requiere_bancarizacion(self, total, fecha_str):
        """
        Determina si se requiere reportar la forma de pago/cobro.
        Desde dic 2023: total >= USD 500
        Antes: total >= USD 1000
        """
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            cambio = datetime.strptime(CAT.FECHA_CAMBIO_BANCARIZACION, '%Y-%m-%d').date()
            limite = CAT.LIMITE_BANCARIZACION_DESDE_DIC2023 if fecha >= cambio else CAT.LIMITE_BANCARIZACION_ANTES
        except Exception:
            limite = CAT.LIMITE_BANCARIZACION_DESDE_DIC2023
        return total >= limite

    def _get_codigo_ret_ir(self, tax):
        """
        Intenta determinar el código de concepto de retención IR del impuesto.
        Busca en el nombre del impuesto un código de 3 dígitos.
        """
        import re
        name = tax.name or ''
        match = re.search(r'\b(\d{3,5})\b', name)
        if match:
            return match.group(1)
        # Fallback por porcentaje
        pct = abs(tax.amount)
        if pct == 1.0:
            return '340'
        elif pct == 2.0:
            return '341'
        elif pct == 8.0:
            return '304'
        elif pct == 10.0:
            return '303'
        elif pct == 25.0:
            return '343'
        return '340'

    def _get_num_estab(self, company):
        """Número de establecimientos del RUC (dígitos 10-13 del RUC)."""
        ruc = self._sanitize_ruc(company.vat)
        if len(ruc) == 13:
            return ruc[10:13]
        return '001'

    def _calcular_totales(self, compras, ventas):
        """Calcula los totales consolidados del período."""
        return {
            'total_ventas_base': sum(v.get('baseImpGrav', 0) + v.get('baseImponible', 0) for v in ventas),
            'total_iva_ventas': sum(v.get('montoIva', 0) for v in ventas),
            'total_compras_base': sum(c.get('baseImpGrav', 0) + c.get('baseImponible', 0) for c in compras),
            'total_iva_compras': sum(c.get('montoIva', 0) for c in compras),
            'total_ret_iva': sum(c.get('valorRetBienes', 0) + c.get('valorRetServicios', 0) for c in compras),
            'total_ret_ir': sum(
                sum(air.get('valorRetenido', 0) for air in c.get('detalleAir', []))
                for c in compras
            ),
            'num_compras': len(compras),
            'num_ventas': len(ventas),
        }

    @staticmethod
    def _sanitize_digits(value):
        return re.sub(r'\D', '', str(value or ''))

    def _sanitize_identifier(self, value, fallback='000'):
        cleaned = re.sub(r'[^A-Za-z0-9]', '', str(value or '')).strip()
        if not cleaned:
            return fallback
        return cleaned[:13]

    def _sanitize_authorization(self, value):
        digits = self._sanitize_digits(value)
        if len(digits) < 3:
            return '000'
        return digits[:49]

    def _sanitize_ruc(self, value):
        digits = self._sanitize_digits(value)
        if len(digits) >= 13:
            digits = digits[:13]
        if len(digits) == 10:
            digits = f'{digits}001'
        if len(digits) != 13:
            return '9999999999001'
        return f'{digits[:10]}001'

    @staticmethod
    def _sanitize_razon_social(value):
        cleaned = re.sub(r'[^A-Za-z0-9 ]', ' ', str(value or '').strip())
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        if len(cleaned) < 5:
            cleaned = (cleaned + ' XXXXX')[:5]
        return cleaned[:500]

    @staticmethod
    def _split_formas_pago(value):
        if not value:
            return []
        raw = str(value).replace(';', ',')
        formas = []
        for token in raw.split(','):
            code = re.sub(r'\D', '', token).zfill(2)
            if len(code) == 2 and code not in formas:
                formas.append(code)
        return formas or ['20']

    @staticmethod
    def _fmt(value):
        """Formatea un número al formato requerido por el ATS (12.2)."""
        try:
            return f'{abs(float(value)):.2f}'
        except (TypeError, ValueError):
            return '0.00'

    @staticmethod
    def _fmt_total(value):
        """
        Formatea totales (totalVentas/ventasEstab/ivaComp), permitiendo signo.
        """
        try:
            return f'{float(value):.2f}'
        except (TypeError, ValueError):
            return '0.00'

    @staticmethod
    def _to_plain_year(value):
        """Normaliza el año a entero puro sin formato (ej. '2026')."""
        try:
            return str(int(float(str(value).strip())))
        except (TypeError, ValueError):
            return str(value).strip()

    @staticmethod
    def _format_date(date_val):
        """Formatea una fecha a DD/MM/YYYY como requiere el ATS."""
        if not date_val:
            return ''
        try:
            if hasattr(date_val, 'strftime'):
                return date_val.strftime('%d/%m/%Y')
            return datetime.strptime(str(date_val), '%Y-%m-%d').strftime('%d/%m/%Y')
        except Exception:
            return str(date_val)
