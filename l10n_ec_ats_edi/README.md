# l10n_ec_ats — Anexo Transaccional Simplificado (ATS) Ecuador

## Descripción

Módulo Odoo para la generación del **ATS del SRI Ecuador**.

A diferencia del Formulario 104 (resumen de casilleros), el ATS es un XML
**transaccional documento por documento**: reporta cada factura, retención,
nota de crédito con todos sus campos conforme al esquema `at.xsd` del SRI.

---

## Diferencias clave ATS vs Formulario 104

| Característica | ATS | F.104 |
|---|---|---|
| Tipo | Transaccional (doc. por doc.) | Resumen (casilleros) |
| Formato | XML (comprimido en .zip) | XML DIMM |
| Presentación | Mensual / semestral | Mensual / semestral |
| Detalle | Proveedor, documento, retención | Solo totales por casillero |
| Complejidad | Alta | Media |

---

## Estructura del XML generado (`at.xsd`)

```xml
<iva>
  <!-- CABECERA -->
  <TipoIDInformante>04</TipoIDInformante>
  <IdInformante>1234567890001</IdInformante>
  <razonSocial>Mi Empresa S.A.</razonSocial>
  <Anio>2025</Anio>
  <Mes>01</Mes>
  <totalVentas>10000.00</totalVentas>
  <codigoOperativo>IVA</codigoOperativo>

  <!-- MÓDULO COMPRAS -->
  <compras>
    <detalleCompras>
      <codSustento>01</codSustento>      <!-- Tabla 9 -->
      <tpIdProv>04</tpIdProv>            <!-- Tabla 1 -->
      <idProv>0987654321001</idProv>
      <tipoComprobante>01</tipoComprobante>  <!-- Tabla 2 -->
      <parteRel>NO</parteRel>
      <fechaRegistro>15/01/2025</fechaRegistro>
      <establecimiento>001</establecimiento>
      <puntoEmision>001</puntoEmision>
      <secuencial>000000123</secuencial>
      <fechaEmision>15/01/2025</fechaEmision>
      <autorizacion>1234567890</autorizacion>
      <baseNoGraIva>0.00</baseNoGraIva>
      <baseImponible>0.00</baseImponible>
      <baseImpGrav>100.00</baseImpGrav>
      <baseImpExe>0.00</baseImpExe>
      <montoIce>0.00</montoIce>
      <montoIva>15.00</montoIva>
      <valRetBien10>0.00</valRetBien10>
      <valRetServ20>0.00</valRetServ20>
      <valorRetBienes>0.00</valorRetBienes>
      <valorRetServicios>10.50</valorRetServicios>
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
      <secRetencion1>000000456</secRetencion1>
      <autRetencion1>9876543210</autRetencion1>
      <fechaEmiRet1>15/01/2025</fechaEmiRet1>
      <formaPago>20</formaPago>           <!-- Tabla 5 — si total >= USD 500 -->
    </detalleCompras>
  </compras>

  <!-- MÓDULO VENTAS -->
  <ventas>
    <detalleVentas>
      <tpIdCliente>04</tpIdCliente>
      <idCliente>1234567890001</idCliente>
      <parteRel>NO</parteRel>
      <tipoComprobante>01</tipoComprobante>
      <tipoEmision>F</tipoEmision>        <!-- F=física, E=electrónica -->
      <numeroComprobantes>1</numeroComprobantes>
      <baseNoGraIva>0.00</baseNoGraIva>
      <baseImponible>0.00</baseImponible>
      <baseImpGrav>500.00</baseImpGrav>
      <montoIva>75.00</montoIva>
      <montoIce>0.00</montoIce>
      <valorRetIva>0.00</valorRetIva>
      <valorRetRenta>0.00</valorRetRenta>
      <formaPago>20</formaPago>
    </detalleVentas>
  </ventas>
</iva>
```

---

## Instalación

```bash
# Dependencias Python
pip install xlsxwriter

# Dependencias Odoo (en __manifest__)
# - account
# - l10n_ec (localización oficial de Ecuador)
# - l10n_ec_base (tipos de identificación LATAM de la localización)

# El código ATS de tipo de identificación (tpIdProv / tpIdCliente / tpIdClienteEx)
# se deriva del campo "Tipo de identificación" del contacto
# (l10n_latam_identification_type_id) vía res.partner._l10n_ec_get_identification_type().
# No se requiere ningún módulo extra de mapeo.
```

---

## Configuración crítica de impuestos

Para que las bases imponibles se clasifiquen correctamente en el ATS:

### En cada impuesto IVA (Contabilidad → Configuración → Impuestos):

| Tipo impuesto | Campo ATS | Cómo identificarlo |
|---|---|---|
| IVA 15% bienes | `baseImpGrav` | tax.amount = 15, nombre contiene "IVA" |
| IVA 0% bienes | `baseImponible` | tax.amount = 0, nombre contiene "IVA" |
| Sin IVA | `baseNoGraIva` | sin impuesto IVA en la línea |

### Código de sustento tributario (`codSustento`)

Configurable en cada factura de proveedor. Si usas OCA `l10n_ec_withhold`,
el campo `l10n_ec_tax_support` ya maneja esto.

Si no tienes OCA, agregar el campo manualmente:
```python
# En una herencia de account.move:
l10n_ec_tax_support = fields.Selection([
    ('01', 'Crédito tributario IVA'),
    ('02', 'Costo/gasto IR'),
    ('03', 'Activo fijo - depreciación IR'),
    ...
], default='01')
```

---

## Reglas clave del ATS 2025

### 1. Documentos electrónicos en módulo ventas
Las facturas, notas de crédito y notas de débito **electrónicas** NO van en
el módulo de ventas si cumplen los formatos XSD vigentes del SRI. El SRI
ya las tiene por el proceso de autorización. En el wizard hay una opción para
incluirlas en caso excepcional.

### 2. Comprobantes de retención electrónicos en compras
A partir de enero 2018, los comprobantes de retención electrónicos **NO** van
en el módulo de compras. El código los filtra automáticamente.

### 3. Bancarización (forma de pago obligatoria)
- Desde 20 dic 2023: total del documento **>= USD 500** → forma de pago obligatoria
- Antes del 20 dic 2023: total **>= USD 1000** → forma de pago obligatoria

### 4. Partes relacionadas
Si el partner tiene `l10n_ec_related_party = True`, el campo `parteRel` se
reporta como `SI`. Configurar en el contacto del partner.

### 5. Exportaciones
Se detectan por el tipo de diario (`l10n_ec_emission_type = 'exportation'`).
Se reportan en el módulo `exportaciones` con tipo de comprobante `10`.

---

## Flujo completo de entrega al SRI

```
1. Generar XML desde Odoo (este módulo)
2. Validar en DIMM (herramienta del SRI)
3. Corregir errores de validación (si los hay)
4. Comprimir el XML en .zip
5. Subir a SRI en Línea → Anexos → ATS
```

---

## Consulta SQL de verificación rápida

```sql
-- Facturas de proveedor sin retención en el período
SELECT m.name, p.name as proveedor, m.amount_total
FROM account_move m
JOIN res_partner p ON p.id = m.partner_id
WHERE m.move_type = 'in_invoice'
  AND m.state = 'posted'
  AND m.company_id = [TU_COMPANY_ID]
  AND m.invoice_date BETWEEN '2025-01-01' AND '2025-01-31'
  AND m.id NOT IN (
    SELECT DISTINCT am.id FROM account_move am
    JOIN account_move ret ON ret.ref = am.name
    WHERE ret.move_type = 'entry'
  )
ORDER BY m.amount_total DESC;
```

---

## Licencia

LGPL-3
