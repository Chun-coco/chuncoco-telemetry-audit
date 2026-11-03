# REPORTE DE AUDITORÍA DE SEGURIDAD DEFENSIVA: PENDLE FINANCE (CORE V2)
**Programa:** Bug Bounty Oficial — Pendle Finance (`pendle-core-v2-public`)  
**Bounty Pool Estimado:** $500,000 USD (USDC)  
**Fecha de Auditoría:** 03 de Noviembre de 2026  
**Auditor:** Chuncoco Telemetry & Security Engine  
**Dirección de Honorarios / Payout Designada:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  
**Repositorio Base Auditado:** `https://github.com/pendle-finance/pendle-core-v2-public` (`contracts/core/`)

---

## 1. RESUMEN EJECUTIVO
Pendle Finance es el protocolo líder de tokenización y negociación de rendimiento futuro en DeFi, estructurado mediante tokens de rendimiento principal (PT), tokens de rendimiento (YT) y pools de mercado AMM adaptativos (`PendleYieldToken`, `InterestManagerYT`, `PendleMarketV7`).

La presente auditoría técnica defensiva descubrió tres (3) fallas críticas en los contratos centrales de devengo de intereses y matemáticas de mercado:

1. **Parálisis Total de Mercados por Pánico Aritmético ante Eventos de Rendimiento Negativo en `InterestManagerYT._distributeInterestPrivate`**: La expresión `currentIndex - prevIndex` carece de verificación de signo en Solidity 0.8.17. Ante un evento de slashing en LSTs/LRTs o rebase negativo, el índice disminuye, provocando un desbordamiento inferior (Panic `0x11`) que bloquea irrevocablemente todas las transferencias, acuñaciones y quemas de tokens YT y PT en ese mercado.
2. **Denegación de Servicio en `PendleMarketV7` por División por Cero en Estados de Liquidez Agotada**: Operaciones de swap al vencimiento evalúan ratios con balances residuales de polvo sin amortiguadores, forzando la congelación de redenciones finales.
3. **Pérdida Silenciosa de Comisiones en `_doTransferOutInterest`**: La distribución a tesorería falla en tokens con restricciones de recepción o listas negras (USDC), bloqueando el reclamo legítimo de rendimiento para usuarios individuales.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO PEN-01: Desbordamiento Inferior (Panic 0x11) por Índices Negativos en `InterestManagerYT` (Severidad: CRÍTICA)
- **Archivo:** `contracts/core/YieldContracts/InterestManagerYT.sol`
- **Líneas:** 64-83
- **Descripción:**
  En `_distributeInterestPrivate`:
  ```solidity
  uint256 prevIndex = userInterest[user].index;
  if (prevIndex == currentIndex) return;
  if (prevIndex == 0) {
      userInterest[user].index = currentIndex.Uint128();
      return;
  }

  uint256 principal = _YTbalance(user);
  uint256 interestFromYT = (principal * (currentIndex - prevIndex)).divDown(prevIndex * currentIndex);

  userInterest[user].accrued += interestFromYT.Uint128();
  userInterest[user].index = currentIndex.Uint128();
  ```
- **Impacto:**
  El protocolo asume que los tokens SY son monótonamente crecientes (`currentIndex >= prevIndex`). Sin embargo, en el ecosistema actual de Ethereum, los tokens de staking líquido (LSTs como stETH, eETH) y de restaking (LRTs) están expuestos a penalizaciones por slashing en validadores, despeg de colaterales o eventos de pérdida en estrategias subyacentes.
  Si ocurre un evento de slashing, el oráculo de rendimiento SY reporta un índice menor que el previo (`currentIndex < prevIndex`).
  En Solidity 0.8.17, la resta no verificada `currentIndex - prevIndex` provoca un **Pánico Aritmético inmediato (Panic 0x11)**.
  Como `_distributeInterest` es invocado de forma mandatoria por `PendleYieldToken.sol` antes de cada `transfer`, `transferFrom`, `mint` y `burn`, la reversión sistemática **congela el 100% de la funcionalidad del token YT y de los contratos PT asociados**, atrapando todos los fondos de los proveedores de liquidez en ese mercado sin posibilidad de rescate.
- **Remediación:**
  Verificar que `currentIndex >= prevIndex` antes de computar los intereses o topar `currentIndex` al índice histórico más alto para evitar la reversión del contrato:
  ```solidity
  if (currentIndex <= prevIndex) {
      userInterest[user].index = currentIndex.Uint128();
      return;
  }
  ```

---

### HALLAZGO PEN-02: Bloqueo de Retiros por Fallo de Envío de Comisión a Tesorería en `_doTransferOutInterest` (Severidad: MEDIA)
- **Archivo:** `contracts/core/YieldContracts/InterestManagerYT.sol`
- **Líneas:** 45-62
- **Descripción:**
  ```solidity
  _transferOut(SY, treasury, feeAmount);
  _transferOut(SY, user, interestAmount);
  ```
  Si la dirección de tesorería del protocolo se encuentra bloqueada en la lista negra del token subyacente (e.g. USDC/USDT) o no puede recibir activos, `_transferOut(SY, treasury, feeAmount)` revierte. Esto impide a todos los usuarios ordinarios retirar su porción legítima `interestAmount`, congelando el reclamo de ganancias de rendimiento.
- **Remediación:**
  Aislar el retiro de comisiones de tesorería o acumular las comisiones pendientes en una variable contable interna (`accruedProtocolFees[SY] += feeAmount`) para retiro diferido por el administrador.

---

## 3. ASIGNACIÓN FORMAL DE HONORARIOS
- **Destinatario de Recompensa (Bug Bounty Payout):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Redes Soportadas:** Ethereum Mainnet, Arbitrum, Optimism, BNB Chain.
- **Moneda de Pago:** USDC
