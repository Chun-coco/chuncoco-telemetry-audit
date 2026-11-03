# REPORTE DE AUDITORÍA DE SEGURIDAD DEFENSIVA: GMX V2 (SYNTHETICS)
**Programa:** Bug Bounty Oficial Immunefi — GMX (`gmx`)  
**Bounty Máximo:** $5,000,000 USD (ETH o USDC)  
**Fecha de Auditoría:** 03 de Noviembre de 2026  
**Auditor:** Chuncoco Telemetry & Security Engine  
**Dirección de Honorarios / Payout Designada:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  
**Repositorio Base Auditado:** `https://github.com/gmx-io/gmx-synthetics` (`contracts/order/`, `contracts/market/`)

---

## 1. RESUMEN EJECUTIVO
GMX v2 es el protocolo descentralizado de intercambio perpetuo y spot que opera con pools de liquidez aislados (GM pools), oráculos firmados de baja latencia y ejecutores descentralizados (*keepers*), administrados a través de bibliotecas modulares (`OrderUtils`, `MarketUtils`, `GasUtils`).

La presente revisión de seguridad defensiva identificó dos (2) inconsistencias operativas críticas en la gestión de tarifas de ejecución y cálculo de gas:

1. **Sobrescritura Silenciosa de Comisiones de Ejecución en `OrderUtils.createOrder`**: `params.numbers.executionFee = wntAmount;` absorbe indiscriminadamente cualquier saldo excedente o donación de WNT presente en `orderVault`, permitiendo que los keepers retiren fondos no declarados del protocolo como comisión inflada.
2. **Desfase en Estimación de Gas L1 en Swaps Multi-hop (`oraclePriceCount`)**: La subestimación de precios oraculares requeridos en rutas complejas de intercambio provoca que las tarifas de ejecución calculadas no cubran el coste de gas en Arbitrum L2, dejando órdenes límite atrapadas en estado no ejecutable.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO GMX-01: Sobrescritura de Tarifa de Ejecución y Drenaje de Fondos en `OrderUtils.createOrder` (Severidad: ALTA)
- **Archivo:** `contracts/order/OrderUtils.sol`
- **Líneas:** 119-126
- **Descripción:**
  Al procesar la tarifa de ejecución en `createOrder`:
  ```solidity
  if (cache.shouldRecordSeparateExecutionFeeTransfer) {
      uint256 wntAmount = orderVault.recordTransferIn(cache.wnt);
      if (wntAmount < params.numbers.executionFee) {
          revert Errors.InsufficientWntAmountForExecutionFee(wntAmount, params.numbers.executionFee);
      }

      params.numbers.executionFee = wntAmount;
  }
  ```
  `orderVault.recordTransferIn(cache.wnt)` calcula la diferencia de saldo de WNT en la bóveda de órdenes. Si por remanentes de transacciones previas, polvo o donaciones en bloque el incremento `wntAmount` supera `params.numbers.executionFee`, el contrato sobreescribe el parámetro del usuario con la totalidad de `wntAmount`.
- **Impacto:**
  La orden queda registrada con una tarifa de ejecución inflada. Cuando el keeper ejecuta la orden, el contrato transfiere la totalidad de `order.executionFee()` al keeper. Fondos que pertenecían a la bóveda o a reembolsos pendientes son absorbidos y transferidos irreversiblemente al operador del keeper.
- **Remediación:**
  Asegurar que la tarifa de ejecución se limite estrictamente a la cantidad especificada por el usuario y que cualquier excedente detectado por `recordTransferIn` se reembolse o se mantenga en custodia:
  ```solidity
  uint256 requiredFee = params.numbers.executionFee;
  if (wntAmount < requiredFee) revert Errors.InsufficientWntAmountForExecutionFee(wntAmount, requiredFee);
  // Mantener params.numbers.executionFee y devolver excedente
  ```

---

## 3. ASIGNACIÓN FORMAL DE HONORARIOS
- **Destinatario de Recompensa (Bug Bounty Payout):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Redes Soportadas:** Arbitrum One, Avalanche.
- **Moneda de Pago:** ETH o USDC (Reglas de Immunefi para GMX).
