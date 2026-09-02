# -*- coding: utf-8 -*-
"""
models/ec_ats_catalogos.py
==========================
Catálogos de códigos del ATS según la Ficha Técnica del SRI Ecuador.
Actualizado: febrero 2025.

FUENTE: Ficha Técnica ATS y Catálogo ATS — sri.gob.ec/formularios-e-instructivos1
"""

# ════════════════════════════════════════════════════════════════
# TABLA 1 — TIPO DE IDENTIFICACIÓN
# ════════════════════════════════════════════════════════════════
TIPO_ID = {
    '04': 'RUC',
    '05': 'Cédula de identidad',
    '06': 'Pasaporte',
    '07': 'Consumidor final',
    '08': 'Identificación exterior / Identificación del exterior',
    '09': 'Placa',
}

# ════════════════════════════════════════════════════════════════
# TABLA 2 — TIPO DE COMPROBANTE
# ════════════════════════════════════════════════════════════════
TIPO_COMPROBANTE = {
    '01': 'Facturas',
    '02': 'Notas de venta - RISE',
    '03': 'Liquidaciones de compra de bienes y prestación de servicios',
    '04': 'Notas de crédito',
    '05': 'Notas de débito',
    '06': 'Guías de remisión',
    '07': 'Comprobantes de retención',
    '08': 'Boletos o entradas a espectáculos públicos',
    '09': 'Tiquetes o vales emitidos por máquinas registradoras',
    '10': 'Documentos de exportación',
    '11': 'Pasajes expedidos por empresas de aviación',
    '12': 'Documentos emitidos por instituciones financieras',
    '15': 'Comprobantes emitidos en el exterior',
    '16': 'Formulario SUNAT-Perú (usado en frontera)',
    '18': 'Documentos autorizados, diferentes de facturas y comprobantes de ventas',
    '19': 'Facturas comerciales negociables',
    '20': 'Estado de cuenta bancario / Tarjeta de crédito',
    '21': 'Carta de porte aéreo (AWB)',
    '22': 'Documentos por servicios de correos',
    '23': 'Formulario de declaración aduanera única (DAU)',
    '24': 'Liquidaciones por servicios del SRI',
    '294': 'Notas de crédito emitidas por instituciones del sistema financiero',
    '344': 'Liquidaciones emitidas por instituciones del sistema financiero',
    '370': 'Documentos emitidos por el SRI',
    '371': 'Recibo de primas de seguros',
    '372': 'Recibo de pago de cuotas o primas de planes de salud',
    '373': 'Ticket de viaje (empresas de transporte terrestre)',
    '374': 'Orden de trabajo',
    '375': 'Facturas de energía eléctrica emitidas por empresas de este sector',
    '376': 'Liquidaciones de compra de bienes - gasolineras',
}

# ════════════════════════════════════════════════════════════════
# TABLA 3 — CONCEPTOS DE RETENCIÓN EN LA FUENTE DE IR (Air)
# Solo los más comunes — lista completa en Catálogo ATS
# ════════════════════════════════════════════════════════════════
CONCEPTOS_IR = {
    # Servicios
    '303': '10% - Honorarios profesionales y dietas',
    '304': '8% - Servicios predomina mano de obra',
    '307': '1% - Servicios entre sociedades',
    '309': '8% - Arrendamiento de bienes inmuebles personas naturales',
    '310': '1% - Arrendamiento de bienes inmuebles sociedades',
    '312': '1% - Transporte privado de pasajeros',
    '319': '1% - Seguros y reaseguros (primas y cesiones)',
    '320': '1% - Rendimientos financieros',
    '321': '2% - Rendimientos financieros (otros)',
    '322': '2% - Intereses por préstamos al exterior',
    '323': '1% - Intereses (instituciones financieras)',
    '325': '1% - Loterías, rifas, apuestas',
    '327': '22% - Dividendos',
    '328': '1% - Distribución de dividendos',
    '330': '25% - Pagos a no residentes - servicios',
    '332': '0% - Compras sin retención (consumidor final)',
    '340': '1% - Otras retenciones aplicables 1%',
    '341': '2% - Otras retenciones aplicables 2%',
    '342': '8% - Otras retenciones aplicables 8%',
    '343': '25% - Otras retenciones aplicables 25%',
    '344': '35% - Retención máxima (paraísos fiscales)',
    '345': '10% - Intereses por mora patronal',
    '346': '10% - Otras retenciones aplicables 10%',
    '347': '15% - Otras retenciones aplicables 15%',
    # Bienes
    '400': '1% - Compra de bienes muebles',
    '401': '1% - Compra de bienes inmuebles',
    '403': '1% - Adquisición de bienes muebles de naturaleza corporal',
    '404': '2% - Transferencia de bienes muebles de naturaleza corporal',
    '405': '1% - Repuestos y herramientas',
    '408': '0% - Compras de bienes exentas de IR',
    '421': '1% - Pagos de bienes inmuebles',
    '422': '1% - Pagos en actividades de construcción de obra material',
    '424': '1% - Suministros y materiales',
    '425': '1% - Repuestos y accesorios',
    '426': '1% - Combustibles derivados del petróleo (gasolineras)',
    '427': '0% - Actividades de exportación',
    '430': '1% - Energía eléctrica',
    '431': '1% - Actividades de construcción de obra material inmueble',
    '440': '1% - Pagos por concepto de obras públicas',
    '500': '22% - Pagos al exterior (sin convenio) - bienes',
    '504': '22% - Pagos al exterior (con convenio) - dividendos',
    '552': '0.5% - Herencias, legados y donaciones',
}

# ════════════════════════════════════════════════════════════════
# TABLA 4 — CÓDIGOS DE RETENCIÓN DE IVA
# ════════════════════════════════════════════════════════════════
CONCEPTOS_IVA = {
    '10': '10% retención IVA - Servicios (bienes)',
    '20': '20% retención IVA - Bienes',
    '30': '30% retención IVA - Bienes',
    '70': '70% retención IVA - Servicios',
    '100': '100% retención IVA - Servicios / liquidaciones',
}

# ════════════════════════════════════════════════════════════════
# TABLA 5 — FORMAS DE PAGO (Compras)
# ════════════════════════════════════════════════════════════════
FORMAS_PAGO = {
    '01': 'Sin utilización del sistema financiero',
    '15': 'Compensación de deudas',
    '16': 'Tarjeta de débito',
    '17': 'Dinero electrónico',
    '18': 'Tarjeta prepago',
    '19': 'Tarjeta de crédito',
    '20': 'Otros con utilización del sistema financiero',
    '21': 'Endoso de títulos',
}

# ════════════════════════════════════════════════════════════════
# TABLA 9 — SUSTENTO TRIBUTARIO (codSustento)
# Obligatorio en el módulo de COMPRAS
# ════════════════════════════════════════════════════════════════
SUSTENTO_TRIBUTARIO = {
    '01': 'Crédito tributario para declaración de IVA',
    '02': 'Costo o gasto para declaración de IR',
    '03': 'Activo fijo - depreciación para declaración de IR',
    '04': 'Liquidación de compras de bienes y servicios',
    '05': 'Pago de bienes o servicios no objeto de IVA',
    '06': 'Pago de bienes o servicios exentos de IVA',
    '07': 'Pago a no residentes - exterior',
    '08': 'Uso o consumo personal por parte del sujeto pasivo del IVA',
    '09': 'Crédito tributario para declaración de IVA (bienes)',
    '10': 'Costo o gasto para declaración de IR (servicios del exterior)',
    '11': 'Crédito tributario en la importación (IVA pagado en importación)',
    '12': 'Sustento para declarar el servicio de televisión por cable',
    '13': 'Sustento para costos o gastos de instituciones del sistema financiero',
    '14': 'Pago al exterior (paraíso fiscal)',
    '15': 'Pago de servicios digitales',
    '16': 'Exportaciones de bienes',
    '17': 'Exportaciones de servicios',
    '18': 'Pago de dividendos',
    '19': 'Costo/gasto deducible por reembolso como intermediario',
}

# ════════════════════════════════════════════════════════════════
# TABLA 13 — FORMAS DE COBRO (Ventas)
# ════════════════════════════════════════════════════════════════
FORMAS_COBRO = {
    '01': 'Sin utilización del sistema financiero',
    '15': 'Compensación de deudas',
    '16': 'Tarjeta de débito',
    '17': 'Dinero electrónico',
    '18': 'Tarjeta prepago',
    '19': 'Tarjeta de crédito',
    '20': 'Otros con utilización del sistema financiero',
    '21': 'Endoso de títulos',
}

# ════════════════════════════════════════════════════════════════
# MAPEO: Tipo de comprobante Odoo → código ATS
# Basado en l10n_ec_edi journal types
# ════════════════════════════════════════════════════════════════
ODOO_MOVE_TYPE_TO_ATS = {
    # Ventas
    'out_invoice': '01',     # Factura cliente → tipo 01
    'out_refund': '04',      # Nota crédito cliente → tipo 04
    # Compras
    'in_invoice': '01',      # Factura proveedor → tipo 01 (por defecto)
    'in_refund': '04',       # Nota crédito proveedor → tipo 04
}

# ════════════════════════════════════════════════════════════════
# LÍMITES BANCARIZACIÓN
# Desde dic 2023: obligatorio reportar forma de pago si total >= 500
# Antes: >= 1000
# ════════════════════════════════════════════════════════════════
LIMITE_BANCARIZACION_DESDE_DIC2023 = 500.0
LIMITE_BANCARIZACION_ANTES = 1000.0
FECHA_CAMBIO_BANCARIZACION = '2023-12-20'

# ════════════════════════════════════════════════════════════════
# REGLAS DE DOCUMENTOS ELECTRÓNICOS
# - Facturas, NC, ND electrónicas NO van en módulo ventas del ATS
#   (ya las tiene el SRI por el proceso de autorización)
# - Comprobantes de retención electrónicos NO van en compras
#   a partir de enero 2018
# ════════════════════════════════════════════════════════════════
FECHA_EXCLUSION_RETENCIONES_ELECTRONICAS = '2018-01-01'
