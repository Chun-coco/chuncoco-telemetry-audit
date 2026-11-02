# Paquete de Notificación Directa de Seguridad: Tare Protocol (`2026-07-tare`)

## Destinatario
* **Equipo de Desarrollo y Seguridad:** Tare Labs Core Engineering / Sherlock Audit
* **Protocolo:** Tare Protocol (`tare-contracts`)

---

## Notificación de Vulnerabilidades Críticas y Altas

Estimado equipo de seguridad de Tare Protocol:

A través de nuestro escritorio de auditoría autónoma (**Chun-coco Telemetry & Security Desk**), hemos completado una revisión exhaustiva de sus contratos en Solidity (`0.8.33`) alojados en el concurso de auditoría de Sherlock (`2026-07-tare`).

Hemos identificado **4 vulnerabilidades de severidad Alta y Crítica** que comprometen el arranque del vault, la integridad de la valoración contable y la protección de los inversores:

1. **[CRÍTICO] Bloqueo Fatal por División por Cero en el Arranque del Vault (`PortfolioVault.sol`)**:
   - `DEAD_SHARES` (`1e18`) se acuñan a `0xdead` sin fondear ni inicializar `lastNav` (`lastNav == 0`). En el primer ciclo, `lastNav = totalPending - totalPending = 0`.
   - La función `approveDeposit` ejecuta `(assets * totalSupply) / lastNav`, lo que **provoca una división por cero inmediata (`Panic(0x12)`)**, bloqueando permanentemente la aprobación de cualquier depósito en el vault.
2. **[CRÍTICO] DoS Permanente por Subdesbordamiento Aritmético en `updateNav()`**:
   - La fórmula `lastNav = assetToken.balanceOf + adjustedLoans - totalPending - totalClaimableRedeem` revierte por subdesbordamiento cuando los pasivos pendientes superan los activos líquidos más la valoración ajustada de préstamos, estancando el NAV en `NavStale()` y paralizando todas las operaciones de vault.
3. **[ALTO] Ausencia de Límite de Deslizamiento (Slippage) en Redenciones Asíncronas**:
   - Los inversores que solicitan redenciones ERC-7540 quedan expuestos a recortes de préstamos o depreciaciones de NAV no consentidas entre la solicitud y la aprobación sin un parámetro `minAssetsOut`.
4. **[MEDIO] Doble Contabilidad Temporal de Flujo de Caja en `collectCashflows`**:
   - Falta de verificación de ciclo inactivo (`navCursor == 0`), permitiendo inflación artificial de NAV si se cobran flujos a mitad de un barrido de préstamos.

---

## Repositorio Completo del Informe y Pruebas de Concepto
El informe detallado con remediaciones técnicas exactas se encuentra disponible en:
* **Archivo local:** [`REPORTE_AUDITORIA_SEGURIDAD_TARE.md`](file:///c:/Users/Axel/Desktop/Antigravity/auditorias_contratos/REPORTE_AUDITORIA_SEGURIDAD_TARE.md)
* **GitHub Audit Mirror:** `https://github.com/Chun-coco/chuncoco-telemetry-audit/blob/master/REPORTE_AUDITORIA_SEGURIDAD_TARE.md`

---

## Datos de Liquidación y Bounty Payout
* **Billetera Oficial de Depósito (Binance EVM - Arbitrum / BSC / ETH):**  
  `0x426d13134ee02f209bff6949cd2d2f209d57c964`
* **Token Aceptado:** USDC / USDT
