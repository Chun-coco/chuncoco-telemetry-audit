# Paquete de Notificación Directa de Seguridad: Cap Labs (`2025-07-cap`)

## Destinatario
* **Equipo de Desarrollo y Seguridad:** Cap Labs Core Architecture / Sherlock Audit
* **Protocolo:** Cap Labs (`cap-contracts`)

---

## Notificación de Vulnerabilidades Críticas y Altas

Estimado equipo de seguridad de Cap Labs:

A través de nuestro escritorio de auditoría autónoma (**Chun-coco Telemetry & Security Desk**), hemos completado una revisión exhaustiva de sus contratos en Solidity (`^0.8.28`) alojados en el repositorio de auditoría de Sherlock (`2025-07-cap`).

Hemos identificado **4 vulnerabilidades de severidad Alta y Crítica** que comprometen la disponibilidad de retiros de usuarios, la integridad del principal en vaults ERC-4626 y la subasta de comisiones del protocolo:

1. **[CRÍTICO] Subdesbordamiento Aritmético en Retiros (`FractionalReserveLogic.sol`)**:
   - `divest($, _asset, _withdrawAmount)` ejecuta `$.loaned[_asset] -= divestAmount;` tras redimir el vault completo cuando `shares > vaultBalance`. Al incluir intereses devengados, `divestAmount > $.loaned[_asset]`, provocando un revert por subdesbordamiento que **bloquea permanentemente los retiros de usuarios**.
   - Adicionalmente, `divest($, _asset)` revierte por pérdidas de 1 wei en el vault subyacente, dejando **brickeada la función administrativa `setFractionalReserveVault()`**.
2. **[ALTO] Drenaje Multiactivo por Precio Único en `FeeAuction.sol`**:
   - `buy()` cobra un solo `price` global pero transfiere el 100% del balance de todos los tokens listados en `_assets`, permitiendo a un bot de MEV extraer múltiples activos acumulados pagando una sola tarifa.
3. **[ALTO] Erosión de Acciones de Principal por Desfase de Redondeo en `realizeInterest`**:
   - `claimableInterest` usa `convertToAssets` (redondeo Floor) mientras que `withdraw` quema acciones usando `previewWithdraw` (redondeo Ceil), quemando acciones del principal prestado en cada ciclo de cosecha.
4. **[MEDIO] DoS en `totalAssets()` de `StakedCap.sol`**:
   - Falta de verificación de desbordamiento en `storedTotal - lockedProfit()`, lo que puede paralizar todas las operaciones de vault si un retiro grande precede la consolidación de recompensas.

---

## Repositorio Completo del Informe y Pruebas de Concepto
El informe detallado con remediaciones técnicas exactas se encuentra disponible en:
* **Archivo local:** [`REPORTE_AUDITORIA_SEGURIDAD_CAP.md`](file:///c:/Users/Axel/Desktop/Antigravity/auditorias_contratos/REPORTE_AUDITORIA_SEGURIDAD_CAP.md)
* **GitHub Audit Mirror:** `https://github.com/Chun-coco/chuncoco-telemetry-audit/blob/master/REPORTE_AUDITORIA_SEGURIDAD_CAP.md`

---

## Datos de Liquidación y Bounty Payout
Para el desembolso de recompensas por divulgación responsable o asignación en el concurso:
* **Billetera Oficial de Depósito (Binance EVM - Arbitrum / BSC / ETH):**  
  `0x426d13134ee02f209bff6949cd2d2f209d57c964`
* **Token Aceptado:** USDC / USDT
