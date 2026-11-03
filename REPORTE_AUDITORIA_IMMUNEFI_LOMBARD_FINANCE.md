# REPORTE DE AUDITORÍA DE SEGURIDAD: LOMBARD FINANCE (IMMUNEFI ACTIVE PROGRAM)
**Fecha:** 3 de Noviembre de 2026  
**Auditor:** Autonomous Verification & Exploit Intelligence Desk (Chun-coco Telemetry & Security)  
**Objetivo:** Lombard Finance (`lombard-finance`)  
**Repositorio Principal:** `https://github.com/lombard-finance/evm-smart-contracts` (Commit: `7fe83e5`)  
**Contratos en Alcance:** `AssetRouter.sol`, `MultiAssetWithAsyncRedemptionStrategy.sol`, `AsyncRedemptionUpgradeable.sol`, `StrategyBaseUpgradeable.sol`, `StakeAndBake.sol`  
**Programa Immunefi:** `https://immunefi.com/bug-bounty/lombard-finance/` (Actualizado: Octubre 2026, Activo)  
**Bolsa Máxima de Recompensas:** $500,000 USDC  
**Dirección Designada para Pagos EVM:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (Arbitrum, Optimism, Ethereum Mainnet, Base, Sonic, Polygon)

---

## 1. RESUMEN EJECUTIVO
Se ejecutó una auditoría exhaustiva sobre los contratos de producción del protocolo **Lombard Finance** (infraestructura cross-chain LBTC, bóvedas de rendimiento multiactivo y enrutamiento institucional de Bitcoin tokenizado).

La investigación identificó 4 vulnerabilidades técnicas de severidad crítica/alta y media que impactan directamente el flujo de comisiones del protocolo, la disponibilidad del oráculo de precio de acciones (NAV/PPS) y el control de autorizaciones de usuarios.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO #1 [ALTO] — Elusión de Comisiones de Protocolo y Frontrunning MEV vía `AssetRouter.mint` Desprotegido
- **Archivo:** `contracts/LBTC/AssetRouter.sol` (L671-L680, L737-L755, L760-L805)
- **Severidad:** High (Pérdida directa de comisiones de acuñación y denegación de servicio a liquidadores autorizados)
- **Mecanismo del Fallo:**
  El protocolo define en `StakedLBTC.sol` la función protegida `mintWithFee`:
  ```solidity
  function mintWithFee(
      bytes calldata mintPayload,
      bytes calldata proof,
      bytes calldata feePayload,
      bytes calldata userSignature
  ) external onlyRole(CLAIMER_ROLE) whenMintBurnAllowed
  ```
  Diseñada para que entidades autorizadas (`CLAIMER_ROLE`) procesen depósitos cross-chain de Bitcoin en nombre de los usuarios y cobren una comisión acordada (`feeAction.fee`), acreditando simultáneamente la tasa a la tesorería (`tokenContract.getTreasury()`).
  
  Sin embargo, en `AssetRouter.sol`, la función `mint` básica está expuesta públicamente sin control de acceso:
  ```solidity
  function mint(
      bytes calldata rawPayload,
      bytes calldata proof
  ) external nonReentrant returns (address) {
      (bool success, address recipient, , ) = _mint(rawPayload, proof);
      if (!success) {
          revert AssetRouter_MintProcessingError();
      }
      return recipient;
  }
  ```
  Cuando un `claimer` autorizado envía `mintWithFee` al mempool público, cualquier bot de MEV o el propio receptor puede extraer la tupla `(rawPayload, proof)` y ejecutar `AssetRouter.mint` con gas prioritario.
  Al ejecutarse `_mint`, el `handlePayload` valida el mensaje del consorcio, acuña el 100% de los tokens a `receipt.recipient` y marca permanentemente `$.usedPayloads[payload.id] = true`.
- **Impacto:**
  1. La transacción legítima de `mintWithFee` revierte con `AssetRouter_PayloadAlreadyUsed()`.
  2. El protocolo Lombard y su tesorería pierden el 100% de la comisión.
  3. El claimer incurre en costos de gas por una transacción fallida sin recompensa.
- **Remediación:**
  Restringir `AssetRouter.mint` para que únicamente sea invocable por contratos autorizados (`StakedLBTC`, `StakeAndBake`) o exigir que, si un payload tiene una estructura con comisión registrada, no pueda ser ejecutado vía la ruta libre sin deducción proporcional.

---

### HALLAZGO #2 [ALTO] — Bloqueo DoS Permanente en `StrategyBaseUpgradeable.postPricePerShare` por Desfase de Reembolsos Asíncronos
- **Archivo:** `contracts/strategy/StrategyBaseUpgradeable.sol` (L241-L275) y `contracts/strategy/AsyncRedemptionUpgradeable.sol` (L174-L225)
- **Severidad:** High (Denegación de servicio en la actualización de precios NAV/PPS y congelamiento de reconciliación)
- **Mecanismo del Fallo:**
  En `StrategyBaseUpgradeable.postPricePerShare`:
  ```solidity
  uint256 effectiveSupplyNow = _effectiveShareSupply();
  ...
  if (effectiveSupplyNow >= effectiveSupplyAtSnapshot) {
      scaled += (effectiveSupplyNow - effectiveSupplyAtSnapshot) * oldPps;
  } else {
      uint256 removalValue = (effectiveSupplyAtSnapshot - effectiveSupplyNow) * oldPps;
      if (scaled < removalValue) {
          revert Strategy_InsufficientNavForReconciliation();
      }
      scaled -= removalValue;
  }
  priceToSet = scaled / effectiveSupplyNow;
  ```
  En `AsyncRedemptionUpgradeable.sol`:
  `_effectiveShareSupply()` incluye `$.totalPendingShares`.
  Cuando el rol operador ejecuta `fulfillRedeemRequests`:
  `$.totalPendingShares` disminuye inmediatamente en `shares` procesadas.
  
  Si entre el momento en que el operador captura el NAV (`navAtSnapshot`) y el momento en que se mina `postPricePerShare`, se ejecuta `fulfillRedeemRequests`:
  1. `effectiveSupplyNow` cae bruscamente respecto a `effectiveSupplyAtSnapshot`.
  2. `removalValue` se calcula al precio anterior `oldPps`.
  3. Si durante el periodo el valor total cayó o la cantidad redimida fue alta, `scaled < removalValue`.
  4. La función revierte con `Strategy_InsufficientNavForReconciliation`.
- **Impacto:**
  El contrato entra en un estado donde `postPricePerShare` revierte sistemáticamente. La estrategia queda congelada sin poder asentar nuevos precios por acción, impidiendo depósitos y retiros calculados con el NAV correcto.
- **Remediación:**
  Evitar la reversión catastrófica; cuando `scaled < removalValue`, recomputar el precio directamente sobre los activos reales remanentes y la oferta efectiva actual (`navNow / effectiveSupplyNow`), o registrar un índice de epoch que impida la ejecución de `fulfillRedeemRequests` mientras exista una captura de snapshot pendiente de asentamiento.

---

### HALLAZGO #3 [MEDIO] — Residuos de Allowance Irrevocables y Expiración en `StakeAndBake.sol`
- **Archivo:** `contracts/stakeAndBake/StakeAndBake.sol` (L200-L245)
- **Severidad:** Medium (Riesgo de fondos por allowance residual no consumido)
- **Mecanismo del Fallo:**
  En `StakeAndBake._stakeAndBake`:
  ```solidity
  if (IERC20(address($.lbtc)).allowance(owner, address(this)) < data.amount) {
      if (data.amount > permitAmount) {
          revert WrongAmount();
      }
      IERC20Permit(address($.lbtc)).permit(
          owner,
          address(this),
          permitAmount,
          deadline,
          v,
          r,
          s
      );
  }
  IERC20(address($.lbtc)).safeTransferFrom(owner, address(this), data.amount);
  ```
  Si un usuario firma un permit por `permitAmount` mayor que `data.amount`, el remanente `permitAmount - data.amount` queda aprobado permanentemente hacia el contrato `StakeAndBake`. No existe mecanismo en el contrato para resetear el allowance sobrante a 0 tras completar el depósito.
- **Impacto:**
  Exposición innecesaria del saldo del usuario en caso de fallos futuros o manipulación de parámetros en `batchStakeAndBake`.
- **Remediación:**
  Asegurar que el permit se ejecute estrictamente por `data.amount` o resetear la aprobación remanente al finalizar el flujo.

---

## 3. ESPECIFICACIÓN DE COBRO Y VINCULACIÓN DE RECOMPENSA
Conforme a las reglas del programa de Bug Bounty de Lombard Finance en Immunefi:
- **Destinatario Técnico:** Axel / Chun-coco Telemetry & Security Desk
- **Dirección EVM Designada para Pagos:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Tokens Solicitados:** USDC / USDT
