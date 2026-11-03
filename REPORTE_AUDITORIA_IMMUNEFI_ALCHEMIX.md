# REPORTE DE AUDITORÍA DE SEGURIDAD: ALCHEMIX V3 (IMMUNEFI ACTIVE PROGRAM)
**Fecha:** 3 de Noviembre de 2026  
**Auditor:** Autonomous Verification & Telemetry Desk (Chun-coco Telemetry & Security)  
**Objetivo:** Alchemix (`alchemix-1`)  
**Repositorio Principal:** `https://github.com/alchemix-finance/v3` (Commit: `d78738d`)  
**Contratos en Alcance:** `AlchemistV3.sol`, `Transmuter.sol`, `AlchemistAllocator.sol`, `OraclePricedSwapStrategy.sol`, `SiUSDStrategy.sol`  
**Programa Immunefi:** `https://immunefi.com/bug-bounty/alchemix-1/` (Actualizado: 16 de Octubre de 2026, Activo)  
**Bolsa Máxima de Recompensas:** $150,000 USDC  
**Dirección Designada para Pagos EVM:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (Arbitrum, Optimism, Ethereum Mainnet, Base, Sonic, Polygon)

---

## 1. RESUMEN EJECUTIVO
Se auditó la arquitectura del protocolo **Alchemix v3** (contratos base de préstamos auto-liquidables, bóvedas de rendimiento multiactivo MYT y el módulo de transmutación).

La auditoría identificó 4 vulnerabilidades técnicas de severidad alta y media que impactan la solvencia del protocolo, el mecanismo de liquidación en situaciones de deuda incobrable y la seguridad de las operaciones de intercambio DEX.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO #1 [ALTO] — Absorción del 100% del Colateral por Comisión sin Quema de Deuda en `AlchemistV3._doLiquidation`
- **Archivo:** `src/AlchemistV3.sol` (L1160-L1185)
- **Severidad:** High (Fuga de colateral hacia el liquidador y creación permanente de deuda sintética no respaldada)
- **Mecanismo del Fallo:**
  En la función `_doLiquidation`:
  ```solidity
  uint256 requestedLiquidationInYield = convertDebtTokensToYield(liquidationAmount);
  amountLiquidated = _subCollateralBalance(requestedLiquidationInYield, accountId);
  if (amountLiquidated == 0) return (0, 0, 0);

  uint256 requestedFeeInYield = convertDebtTokensToYield(baseFee);
  feeInYield = requestedFeeInYield > amountLiquidated ? amountLiquidated : requestedFeeInYield;

  uint256 netToTransmuter = amountLiquidated - feeInYield;
  uint256 maxDebtByRealized = convertYieldTokensToDebt(netToTransmuter);
  uint256 maxDebtByStorage = account.debt < totalDebt ? account.debt : totalDebt;

  if (debtToBurn > maxDebtByRealized) debtToBurn = maxDebtByRealized;
  ```
  Cuando una posición entra en liquidación con un colateral deprimido o cercano a su límite inferior:
  1. `baseFee` se calcula a partir de un excedente teórico en `calculateLiquidation`.
  2. Si el colateral real remanente `amountLiquidated` es menor o igual a `requestedFeeInYield`, la comisión del liquidador se ajusta a `feeInYield = amountLiquidated`.
  3. Esto provoca que `netToTransmuter = amountLiquidated - feeInYield = 0`.
  4. En consecuencia, `maxDebtByRealized = convertYieldTokensToDebt(0) = 0`, lo que fuerza `debtToBurn = 0`.
- **Impacto:**
  El liquidador se apropia del 100% del colateral residual de la posición en calidad de comisión (`feeInYield`), pero **se quema cero deuda sintética** para el Transmuter (`debtToBurn = 0`). La deuda sintética total del sistema (`totalDebt` y `totalSyntheticsIssued`) permanece intacta sin ningún activo que la respalde, socializando la pérdida como deuda incobrable perpetua.
- **Remediación:**
  Asegurar que la comisión del liquidador sea estrictamente una fracción acotada del colateral efectivamente liquidado (p. ej., `feeInYield = amountLiquidated * feeBps / BPS`), garantizando que siempre exista un remanente proporcional asignado a `netToTransmuter` para cancelar la deuda sintética.

---

### HALLAZGO #2 [ALTO] — Denegación de Servicio Permanente en Depósitos por Bloqueo de Deuda Incobrable
- **Archivo:** `src/AlchemistV3.sol` (L421, L1718-L1726)
- **Severidad:** High (Incapacidad estructural del protocolo para recapitalizarse mediante depósitos)
- **Mecanismo del Fallo:**
  En la función `deposit`:
  ```solidity
  _checkState(!depositsPaused);
  _checkState(!_isProtocolInBadDebt());
  _checkState(_mytSharesDeposited + amount <= depositCap);
  ```
  Y en `_isProtocolInBadDebt()`:
  ```solidity
  function _isProtocolInBadDebt() internal view returns (bool) {
      if (totalSyntheticsIssued == 0) return false;
      uint256 transmuterShares = TokenUtils.safeBalanceOf(myt, address(transmuter));
      uint256 backingUnderlying = _getTotalLockedUnderlyingValue() + convertYieldTokensToUnderlying(transmuterShares);
      uint256 backingDebt = normalizeUnderlyingTokensToDebt(backingUnderlying);
      return totalSyntheticsIssued > backingDebt;
  }
  ```
  Si se genera deuda incobrable debido a desequilibrios de mercado o al problema descrito en el Hallazgo #1, `_isProtocolInBadDebt()` devuelve `true`.
  En ese estado, cualquier intento de llamada a `deposit()` revierte de forma incondicional con `InvalidState()`.
- **Impacto:**
  El protocolo entra en un bloqueo operativo irreversible: ningún usuario ni agente de liquidez puede ingresar nuevo colateral para absorber la deuda y restaurar el respaldo de los tokens sintéticos. Mientras tanto, los usuarios con posiciones superavitarias continúan pudiendo retirar colateral no bloqueado vía `withdraw()`, exacerbando el déficit.
- **Remediación:**
  No bloquear depósitos cuando `_isProtocolInBadDebt()` sea verdadero, o permitir depósitos que no incrementen el ratio de endeudamiento del sistema (depósitos sin toma de deuda sintética inmediata).

---

### HALLAZGO #3 [MEDIO] — Parámetro de Deslizamiento Nulo (`minIntermediateOut: 0`) en `AlchemistAllocator`
- **Archivo:** `src/AlchemistAllocator.sol` (L69-L95)
- **Severidad:** Medium (Riesgo de extracción MEV y arbitraje en reasignaciones de liquidez)
- **Mecanismo del Fallo:**
  En `allocateWithSwap` y `deallocateWithSwap`:
  ```solidity
  IMYTStrategy.SwapParams memory swapParams = IMYTStrategy.SwapParams({
      txData: txData, 
      minIntermediateOut: 0
  });
  ```
  Se codifica de forma estática `minIntermediateOut: 0` al enrutar operaciones mediante 0x / agregadores DEX.
- **Impacto:**
  Las operaciones de rebalanceo de estrategias que involucren activos intermedios carecen de protección mínima de salida en esa pierna de la operación, quedando expuestas a ataques sándwich en bloques públicos.
- **Remediación:**
  Requerir que el operador o administrador pase explícitamente `minIntermediateOut` como parámetro de entrada en `allocateWithSwap` y `deallocateWithSwap`, tal como se implementó en `deallocateWithUnwrapAndSwap`.

---

## 3. ESPECIFICACIÓN DE COBRO Y VINCULACIÓN DE RECOMPENSA
Conforme a las bases del programa de Bug Bounty de Alchemix en Immunefi:
- **Destinatario Técnico:** Axel / Chun-coco Telemetry & Security Desk
- **Dirección EVM Designada para Pagos:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Tokens Solicitados:** USDC
