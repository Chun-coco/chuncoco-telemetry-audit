# REPORTE DE AUDITORÍA DE SEGURIDAD: COW PROTOCOL (IMMUNEFI ACTIVE PROGRAM)
**Fecha:** 3 de Noviembre de 2026  
**Auditor:** Autonomous Exploit Intelligence & Verification Desk (Chun-coco Telemetry & Security)  
**Objetivo:** CoW Protocol (`cowprotocol`)  
**Repositorio Principal:** `https://github.com/cowprotocol/contracts` (Commit: `c07a93e`)  
**Contratos en Alcance:** `GPv2Settlement.sol`, `GPv2VaultRelayer.sol`, `GPv2Transfer.sol`, `GPv2AllowListAuthentication.sol`, `GPv2Trade.sol`  
**Programa Immunefi:** `https://immunefi.com/bug-bounty/cowprotocol/` (Actualizado: 30 de Octubre de 2026, Activo)  
**Bolsa Máxima de Recompensas:** $1,000,000 USDC  
**Dirección Designada para Pagos EVM:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (Arbitrum, Optimism, Ethereum Mainnet, Base, Sonic, Polygon)

---

## 1. RESUMEN EJECUTIVO
Se auditó la arquitectura del motor de liquidación descentralizado por lotes **CoW Protocol (CoW Swap / Gnosis Protocol v2)**.
Se identificaron 3 vulnerabilidades técnicas clave:
1. Denegación de servicio (DoS) en la liquidación por lotes debido al uso del opcode legacy `.transfer()` con estipendio fijo de 2,300 gas para transferencias nativas de ETH a Smart Contract Wallets (Safe, ERC-4337).
2. Desbordamiento aritmético en `SafeMath.mul` durante la verificación de precios límite para tokens con suministros elevados o números altos de decimales.
3. Drenaje gradual de comisiones de liquidación acumuladas mediante redondeo asimétrico (`ceilDiv` en compras y `div` en ventas).

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO #1 [ALTO] — Denegación de Servicio en Liquidación por Lotes de ETH vía `.transfer()` Restringido a 2,300 Gas
- **Archivo:** `src/contracts/libraries/GPv2Transfer.sol` (L183-L191)
- **Severidad:** High (Denegación de servicio que bloquea la ejecución de lotes enteros de intercambio en producción)
- **Mecanismo del Fallo:**
  En la función `transferToAccounts`:
  ```solidity
  if (address(transfer.token) == BUY_ETH_ADDRESS) {
      require(
          transfer.balance != GPv2Order.BALANCE_INTERNAL,
          "GPv2: unsupported internal ETH"
      );
      payable(transfer.account).transfer(transfer.amount);
  }
  ```
  El método `.transfer()` reenvía un límite rígido de **2,300 unidades de gas**.
  Si un usuario envía una orden de compra donde el activo resultante es Ether (`BUY_ETH_ADDRESS = 0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE`) y el destinatario `transfer.account` es:
  - Una billetera multifirma (Gnosis Safe / Safe Wallet)
  - Una cuenta inteligente con Abstracción de Cuenta (ERC-4337)
  - Un contrato que ejecuta lógica de registro o emite eventos en `receive()` (lo cual consume > 2,300 gas)
  - Un contrato en redes L2 (Arbitrum, Base, Optimism) donde el costo de opcodes difiere del estándar original de Ethereum
  
  La llamada `.transfer()` falla por Out of Gas y revierte de forma irrecuperable.
  Dado que `vault.transferToAccounts(outTransfers)` se invoca sincrónicamente dentro de `GPv2Settlement.settle`, el fallo de una sola orden con destino ETH a un Smart Contract Wallet aborta la transacción completa del lote, penalizando al solver que asumió el costo de gas del bloque.
- **Impacto:**
  Incompatibilidad crítica con contratos inteligentes y Smart Wallets institucionales, provocando reversiones masivas en transacciones de batch settlement.
- **Remediación:**
  Sustituir `.transfer()` por una llamada de bajo nivel con control de gas:
  ```solidity
  (bool success, ) = payable(transfer.account).call{value: transfer.amount}("");
  require(success, "GPv2: ETH transfer failed");
  ```
  La función ya está protegida contra reentrancia mediante el modificador `nonReentrant` en `GPv2Settlement.settle`.

---

### HALLAZGO #2 [ALTO] — Desbordamiento en Verificación de Precios Límite para Tokens de Alto Suministro
- **Archivo:** `src/contracts/GPv2Settlement.sol` (L362-L365)
- **Severidad:** High (Reversión sistemática en la liquidación de tokens meme o de gran capitalización decimal)
- **Mecanismo del Fallo:**
  En `computeTradeExecution`:
  ```solidity
  require(
      order.sellAmount.mul(sellPrice) >= order.buyAmount.mul(buyPrice),
      "GPv2: limit price not respected"
  );
  ```
  `SafeMath.mul` revierte con `"SafeMath: multiplication overflow"` si `order.sellAmount * sellPrice > type(uint256).max` (~1.157 * 10^77).
  Para tokens con suministros muy altos (p. ej. memecoins con suministros de 10^27 o tokens con 18-27 decimales) multiplicados por precios de compensación escalados a 10^18 o superiores, el producto excede 2^256 - 1, provocando reversión inmediata en la verificación de precios límite.
- **Remediación:**
  Implementar multiplicación intermedia de 512 bits (utilizando librerías tipo `FullMath.mulDiv`) o normalizar los órdenes de magnitud antes de la comparación.

---

### HALLAZGO #3 [MEDIO] — Asimetría de Redondeo que Drena Saldos de la Bóveda de Liquidación
- **Archivo:** `src/contracts/GPv2Settlement.sol` (L390, L413)
- **Severidad:** Medium (Déficit acumulativo que consume fondos de comisiones del contrato)
- **Mecanismo del Fallo:**
  - Órdenes Sell: `executedBuyAmount = executedSellAmount.mul(sellPrice).ceilDiv(buyPrice);` (Redondeo hacia arriba del importe a entregar al usuario).
  - Órdenes Buy: `executedSellAmount = executedBuyAmount.mul(buyPrice).div(sellPrice);` (Redondeo hacia abajo del importe cobrado al usuario).
  Ambos cálculos transfieren las fracciones de wei a favor del usuario final y en contra del contrato de liquidación. En entornos de alta frecuencia con millones de intercambios, esto genera una discrepancia acumulativa que agota las comisiones retenidas en `GPv2Settlement`.
- **Remediación:**
  Unificar el sentido de redondeo a favor del protocolo (`div` para compras y `ceilDiv` para cobros de venta) para preservar la solvencia estricta de la bóveda.

---

## 3. ESPECIFICACIÓN DE COBRO Y VINCULACIÓN DE RECOMPENSA
Conforme a los lineamientos del programa de Bug Bounty de CoW Protocol en Immunefi:
- **Destinatario Técnico:** Axel / Chun-coco Telemetry & Security Desk
- **Dirección EVM Designada para Pagos:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Tokens Solicitados:** USDC
