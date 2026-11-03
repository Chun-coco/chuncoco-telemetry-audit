# REPORTE DE AUDITORÍA DE SEGURIDAD DEFENSIVA: SYNTHETIX V3 CORE
**Programa:** Bug Bounty Oficial Immunefi — Synthetix (`synthetix`)  
**Bounty Máximo:** $100,000 USD (USD)  
**Fecha de Auditoría:** 03 de Noviembre de 2026  
**Auditor:** Chuncoco Telemetry & Security Engine  
**Dirección de Honorarios / Payout Designada:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  
**Repositorio Base Auditado:** `https://github.com/Synthetixio/synthetix-v3` (`protocol/synthetix/contracts/modules/core/`)

---

## 1. RESUMEN EJECUTIVO
Synthetix v3 es el protocolo modular de liquidez y derivados sintéticos que permite la creación de pools de colateral compartido, mercados spot/perpetuos y emisión de snxUSD (`LiquidationModule`, `VaultModule`, `CollateralModule`).

La presente revisión de seguridad defensiva identificó tres (3) vectores críticos en la lógica de liquidación y redistribución de colateral:

1. **Escalamiento Negativo de Colateral en `LiquidationModule.liquidate`**: Si la recompensa fija de liquidación supera el colateral liquidado de una posición individual, la función `scale` se invierte aritméticamente, deduciendo colateral del resto de las posiciones del vault.
2. **Espiral de Liquidación en Cascada por Socialización Inmediata de Deuda**: La redistribución forzosa de la deuda incobrable entre cuentas que operan cerca del ratio de liquidación induce liquidaciones en cadena en el mismo bloque.
3. **Desfase de Precios y Dilución de Capacidad en Mercados Derivados (`recalculateVaultCollateral`)**: La actualización asíncrona de capacidad post-liquidación permite la ejecución de retiros de liquidez con precios desactualizados de colateral.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO SNX-01: Escalamiento Negativo de Colateral en `LiquidationModule` (Severidad: ALTA)
- **Archivo:** `protocol/synthetix/contracts/modules/core/LiquidationModule.sol`
- **Líneas:** 101-125
- **Descripción:**
  En `LiquidationModule.liquidate`:
  ```solidity
  liquidationData.amountRewarded = collateralConfig.liquidationRewardD18;
  if (liquidationData.amountRewarded >= epoch.collateralAmounts.totalAmount()) {
      revert MustBeVaultLiquidated();
  }
  ...
  epoch.collateralAmounts.scale(
      liquidationData.collateralLiquidated.toInt() - liquidationData.amountRewarded.toInt()
  );
  ```
- **Impacto:**
  La verificación de guardia en la línea 102 valida que `amountRewarded` sea menor que el colateral TOTAL del vault (`epoch.collateralAmounts.totalAmount()`), pero **NO valida** que sea menor que el colateral de la cuenta específica liquidada (`liquidationData.collateralLiquidated`).
  Si una posición pequeña se liquida con `collateralLiquidated < amountRewarded`:
  $$\text{colateralADistribuir} = \text{collateralLiquidated} - \text{amountRewarded} < 0$$
  La función `scale` recibe un valor negativo. En lugar de distribuir colateral excedente a los restantes stakers del vault, el colateral de los usuarios inocentes se reduce arbitrariamente para subsidiar la recompensa del liquidador.
- **Remediación:**
  Topar la recompensa del liquidador al colateral disponible en la cuenta o derivar la recompensa como un porcentaje del colateral liquidado:
  ```solidity
  uint256 reward = collateralConfig.liquidationRewardD18 > liquidationData.collateralLiquidated
      ? liquidationData.collateralLiquidated
      : collateralConfig.liquidationRewardD18;
  ```

---

### HALLAZGO SNX-02: Espiral de Liquidación por Socialización Forzada de Deuda (Severidad: MEDIA-ALTA)
- **Archivo:** `protocol/synthetix/contracts/modules/core/LiquidationModule.sol`
- **Líneas:** 126-131
- **Descripción:**
  Al liquidar una posición, la deuda completa se remueve de la cuenta liquidada y se distribuye entre todas las demás cuentas del vault:
  ```solidity
  epoch.distributeDebtToAccounts(liquidationData.debtLiquidated.toInt());
  ```
- **Impacto:**
  En momentos de alta volatilidad del mercado, las posiciones de los demás stakers que mantienen ratios de colateralización apenas superiores al umbral mínimo (`liquidationRatioD18`) reciben repentinamente una asignación imprevista de deuda. Esto reduce instantáneamente su C-Ratio por debajo del límite de liquidación, permitiendo que liquidadores las ataquen en cascada en la misma transacción o bloque, liquidando vaults enteros y socializando deudas incobrables masivas.
- **Remediación:**
  Absorber la deuda mediante un fondo de amortización o imponer un periodo de gracia (amortization buffer) para que los stakers secundarios puedan aportar colateral antes de ser elegibles para liquidación.

---

## 3. ASIGNACIÓN FORMAL DE HONORARIOS
- **Destinatario de Recompensa (Bug Bounty Payout):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Redes Soportadas:** Ethereum Mainnet, Optimism, Base, Arbitrum.
- **Moneda de Pago:** USD (USDC/sUSD)
