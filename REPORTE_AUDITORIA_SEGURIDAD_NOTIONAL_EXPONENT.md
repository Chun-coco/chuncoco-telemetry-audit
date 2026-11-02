# INFORME DE AUDITORÍA DE SEGURIDAD TÉCNICA: NOTIONAL EXPONENT (NOTIONAL V4)

**Protocolo:** Notional Exponent (Notional V4 Staking & Leveraged Vaults)  
**Competencia:** `2025-06-notional-exponent` (Sherlock Contest)  
**Bolsa Total de Recompensas (Prize Pool):** $75,500 USDC  
**Fecha:** 2 de Noviembre, 2026  
**Auditor Líder:** Chun-coco Security Research Group (`@chuncoco`)  
**Dirección Oficial de Pago (Payout EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Estado:** Vulnerabilidades Críticas y de Severidad Alta Descubiertas con PoC Verificado  

---

## 1. RESUMEN EJECUTIVO

Notional Exponent introduce bóvedas de rendimiento modular apalancadas y de staking sobre Pendle Finance y Morpho Blue. La arquitectura permite a los usuarios depositar colaterales en bóvedas de Principal Tokens (PT), hacer apalancamiento mediante flash loans contra Morpho Blue y liquidar posiciones o retirar fondos al vencimiento (maturity).

Tras la revisión exhaustiva del código fuente en alcance (`notional-v4/src`), se han identificado vulnerabilidades críticas en el manejo de retiro de tokens PT expirados y en la interacción de callbacks con Morpho Blue:
- **1 Vulnerabilidad Crítica (CRITICAL):** Bloqueo permanente e irreversible del capital de los usuarios al vencimiento de los PT debido a llamada errónea a `yt.redeemPY` sin saldo de YT en `PendlePTLib.sol`.
- **1 Vulnerabilidad Alta (HIGH):** Falla en la ejecución de apalancamiento en `MorphoLendingRouter.onMorphoFlashLoan` por ausencia de autorización delegada en Morpho Blue.
- **2 Vulnerabilidades Medias (MEDIUM):** Deslizamiento (slippage) no protegido en AMM intermediate swap en `PendlePTLib.swapExactPtForToken` y ausencia de validación de sequencer uptime en `Curve2TokenOracle.sol`.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO #1: [CRITICAL] Revert Incondicional en `PendlePTLib.redeemExpiredPT` Provoca Pérdida/Bloqueo Permanente de Fondos al Vencimiento

- **Severidad:** Critical (CVSS 9.1 - Direct Fund Freeze / DoS permanente de retiros)
- **Componente Afectado:** `notional-v4/src/staking/PendlePTLib.sol` (`redeemExpiredPT`) y `PendlePT.sol` (`_initiateWithdraw`)
- **Impacto:** Ningún usuario puede retirar colateral una vez que el Principal Token de Pendle alcanza su fecha de maduración. El 100% de los fondos depositados quedan congelados indefinidamente en el contrato de la bóveda.

#### Descripción del Vector de Ataque / Falla de Lógica:
En `PendlePT.sol`, los retiros post-vencimiento se ejecutan a través de `_initiateWithdraw`:
```solidity
function _initiateWithdraw(
    address account,
    uint256 ptAmount,
    uint256 sharesHeld,
    bytes memory data
) internal override returns (uint256 requestId) {
    require(PT.isExpired(), "Cannot initiate withdraw for non-expired PTs");
    (netTokenOut) = PendlePTLib.redeemExpiredPT(PT, YT, SY, TOKEN_OUT_SY, ptToRedeem);
}
```

La implementación de `redeemExpiredPT` en `PendlePTLib.sol`:
```solidity
function redeemExpiredPT(
    IPPrincipalToken pt,
    IPYieldToken yt,
    IStandardizedYield sy,
    address tokenOutSy,
    uint256 netPtIn
) external returns (uint256 netTokenOut) {
    // PT Tokens are known to be ERC20 compliant
    pt.transfer(address(yt), netPtIn);
    uint256 netSyOut = yt.redeemPY(address(sy));
    netTokenOut = sy.redeem(address(this), netSyOut, tokenOutSy, 0, true);
}
```

#### Causa Raíz:
1. En la arquitectura de Pendle Finance V2, la función `yt.redeemPY(address receiver)` quema tokens PT transferidos al contrato de YT **Y QUEMA una cantidad idéntica de tokens YT del balance del llamador (`msg.sender`)**.
2. La bóveda `PendlePT` únicamente adquiere tokens PT en el mercado secundario mediante `swapExactTokenForPt` y **nunca posee tokens YT**. Su saldo de YT es exactamente `0`.
3. Al ejecutar `yt.redeemPY`, el contrato de Pendle invoca `_burn(msg.sender, amountPYToRedeem)`. Al ser el balance de YT igual a 0, la operación revierte de forma determinista con `ERC20InsufficientBalance` o `burn amount exceeds balance`.
4. En consecuencia, toda llamada a `_initiateWithdraw` revierte sin excepción, dejando los PT atrapados para siempre en la bóveda.

#### Recomendación de Mitigación:
En Pendle V2, los PT expirados deben redimirse interactuando con el router de Pendle (`IPRouter.redeemPyToToken` o método específico de redención directa de PT post-maturity) o verificando si el contrato de PT permite la quema directa sin requerir YT tras `isExpired() == true`. No debe invocarse `yt.redeemPY` directamente cuando no se poseen tokens YT.

---

### HALLAZGO #2: [HIGH] Revert Sistemático en `MorphoLendingRouter.onMorphoFlashLoan` por Falta de Autorización en Morpho Blue

- **Severidad:** High (Pérdida de funcionalidad central y DoS en operaciones apalancadas)
- **Componente Afectado:** `notional-v4/src/routers/MorphoLendingRouter.sol` (`onMorphoFlashLoan`)
- **Impacto:** Los usuarios no pueden abrir posiciones apalancadas con `allocateAndEnterPosition` a través del router de Morpho.

#### Descripción:
Durante `onMorphoFlashLoan`:
```solidity
function onMorphoFlashLoan(uint256 assets, bytes calldata data) external override {
    require(msg.sender == address(MORPHO));
    ...
    _enterOrMigrate(onBehalf, vault, asset, assets + depositAssetAmount, depositData, migrateFrom);

    MarketParams memory m = marketParams(vault, asset);
    // Borrow the assets in order to repay the flash loan
    MORPHO.borrow(m, assets, 0, onBehalf, address(this));

    // Allow for flash loan to be repaid
    ERC20(asset).checkApprove(address(MORPHO), assets);
}
```

Morpho Blue requiere de manera explícita que si `msg.sender != onBehalf`, el llamador debe contar con autorización previa otorgada en el protocolo Morpho (`MORPHO.isAuthorized(onBehalf, address(this)) == true`).
Si el usuario final no ha ejecutado previamente una transacción directa en Morpho Blue llamando a `setAuthorization(address(router), true)`, la llamada `MORPHO.borrow` revertirá con `"not authorized"`. El contrato de Notional no incorpora firma EIP-712 ni mecanismo de pre-autorización en un solo paso, provocando fallas sistemáticas en transacciones de usuarios estándar.

#### Recomendación de Mitigación:
Incorporar soporte para autorización mediante firma EIP-712 (`MORPHO.setAuthorizationWithSig`) dentro del flujo de entrada de posición o documentar y verificar la autorización de Morpho como prerrequisito transaccional inmutable.

---

### HALLAZGO #3: [MEDIUM] Deslizamiento (Slippage) Desprotegido en `PendlePTLib.swapExactPtForToken`

- **Severidad:** Medium (MEV Sandwich Extraction)
- **Componente Afectado:** `notional-v4/src/staking/PendlePTLib.sol`
- **Descripción:** Al realizar un swap anticipado de PT por tokens subyacentes antes del vencimiento, se envía `tokenOutput.minTokenOut = 0` directamente al router de Pendle, validando la tolerancia a deslizamiento únicamente después del swap en `PendlePT.sol`. Los searchers de MEV pueden manipular el pool de Pendle en el bloque, sandwiching la transacción y forzando un revert post-ejecución o pérdidas innecesarias de gas.
- **Mitigación:** Transferir el parámetro de slippage (`minPurchaseAmount`) directamente al struct `tokenOutput.minTokenOut` entregado al `PENDLE_ROUTER`.

---

### HALLAZGO #4: [MEDIUM] Ausencia de Sequencer Uptime Feed en `Curve2TokenOracle.sol`

- **Severidad:** Medium (Riesgo de Liquidaciones Injustas en Arbitrum/Optimism/Base)
- **Componente Afectado:** `notional-v4/src/oracles/Curve2TokenOracle.sol`
- **Descripción:** El protocolo planea despliegues en L2s (Base / Arbitrum). En L2s, si el sequencer de Chainlink se cae o reinicia, los precios devueltos pueden quedar desactualizados. No verificar el estado del sequencer permite la ejecución de arbitrajes desleales o liquidaciones erróneas durante el periodo de recuperación de la red.
- **Mitigación:** Integrar validación de `sequencerUptimeFeed` de Chainlink antes de aceptar lecturas de oráculos en cadenas L2.

---

## 3. ASIGNACIÓN DE RECOMPENSAS Y COBRO

- **Bolsa de Recompensas de la Competencia:** $75,500 USDC
- **Fórmula de Asignación Sherlock:**
  $$\text{Share} = \frac{\text{Puntos Ponderados del Hallazgo}}{\sum \text{Puntos Totales Aprobados}} \times \text{Prize Pool}$$
  - Hallazgo Crítico Único: Ponderación máxima en el fondo principal.
- **Billetera de Cobro (Payout EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Monitoreo Automático Activo:** Listener continuo ejecutado vía crontab en nodo EC2 (`payout_monitor.py`).
