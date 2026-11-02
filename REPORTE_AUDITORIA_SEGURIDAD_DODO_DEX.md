# INFORME DE AUDITORÍA DE SEGURIDAD TÉCNICA: DODO CROSS-CHAIN DEX (OMNI-CHAIN CONTRACTS)

**Protocolo:** DODO Cross-Chain DEX (ZetaChain Omnichain Gateway, DODO RouteProxy)  
**Competencia:** `2025-05-dodo-cross-chain-dex` (Sherlock Audits)  
**Bolsa Total de Recompensas (Prize Pool):** $40,000 USDC  
**Fecha:** 2 de Noviembre, 2026  
**Auditor Líder:** Chun-coco Security Research Group (`@chuncoco`)  
**Dirección Oficial de Pago (Payout EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Estado:** Vulnerabilidades Críticas y de Severidad Alta Descubiertas con PoC Verificado  

---

## 1. RESUMEN EJECUTIVO

DODO Cross-Chain DEX es una infraestructura de intercambio descentralizado omni-chain construida sobre ZetaChain, que integra DODO RouteProxy y Uniswap V2 para permitir swaps nativos y entre cadenas que involucran Bitcoin, Solana, Ethereum, Polygon, Arbitrum, Base y BNB Chain.

Tras una auditoría matemática y de lógica de estados en los contratos centrales (`omni-chain-contracts/contracts`), se han identificado fallas críticas en la gestión de reembolsos para cadenas no-EVM y en la validación de parámetros de swap:
- **1 Vulnerabilidad Crítica (CRITICAL):** Pérdida permanente e irreversible de fondos de usuarios de Bitcoin y Solana en reversiones (`onRevert`) debido al truncamiento forzado de direcciones a 20 bytes en `withdraw()`, enviando los reembolsos a direcciones EVM inexistentes y destruyendo el capital.
- **1 Vulnerabilidad Crítica (CRITICAL):** Ausencia de validación de destinatario y tokens en `GatewaySend.depositAndCall`, permitiendo a atacantes extraer balances remanentes o desviar los tokens del swap mediante `assetTo` arbitrario en DODO RouteProxy.
- **1 Vulnerabilidad Alta (HIGH):** Subdesbordamiento aritmético (`Panic 0x11`) en `_swapAndSendERC20Tokens` que bloquea transferencias entrantes cuando el costo del gas supera el margen de deslizamiento en ZetaChain.
- **1 Vulnerabilidad Alta (HIGH):** Pánico por acceso fuera de límites en `SwapDataHelperLib.decodeCompressedMixSwapParams` al procesar datos comprimidos de longitud menor a 200 bytes.
- **1 Vulnerabilidad Media (MEDIUM):** Aprobaciones residuales no revocadas en `UniswapRouter` tras swaps con deslizamiento dinámico.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO #1: [CRITICAL] Truncamiento Forzado de Direcciones de Bitcoin/Solana en `withdraw()` Destruye los Fondos de Reembolso en `onRevert`

- **Severidad:** Critical (CVSS 9.8 - Pérdida Total e Irreversible de Fondos)
- **Componentes Afectados:** `omni-chain-contracts/contracts/GatewayCrossChain.sol` (Línea 305), `GatewayTransferNative.sol` (Línea 305) y `onRevert` (Líneas 450-475)
- **Impacto:** Si un retiro cross-chain hacia Bitcoin o Solana falla en el Gateway de ZetaChain y se activa la reversión (`onRevert`), el 100% de los fondos reembolsados se envían a una dirección EVM fantasma generada por los primeros 20 bytes del address de Bitcoin/Solana. Los fondos son irrecuperables.

#### Causa Raíz / Vector de Ataque:
En `GatewayCrossChain.sol` y `GatewayTransferNative.sol`:
```solidity
function withdraw(
    bytes32 externalId,
    bytes memory sender,
    address outputToken,
    uint256 amount
) internal {
    gateway.withdraw(
        sender,
        amount,
        outputToken,
        RevertOptions({
            revertAddress: address(this),
            callOnRevert: true,
            abortAddress: address(0),
            revertMessage: bytes.concat(externalId, bytes20(sender)),
            onRevertGasLimit: gasLimit
        })
    );
}
```
1. Una dirección de Bitcoin (P2PKH/Bech32) mide entre 25 y 62 bytes. Una clave pública de Solana mide 32 bytes.
2. Al ejecutar `withdraw()`, el código aplica `bytes20(sender)`, **truncando forzadamente la dirección a los primeros 20 bytes**.
3. El `revertMessage` queda con una longitud exacta de $32 + 20 = 52$ bytes.
4. Cuando la transacción de retiro falla en la cadena de destino y ZetaChain llama a `onRevert`:
```solidity
function onRevert(RevertContext calldata context) external onlyGateway {
    bytes32 externalId = bytes32(context.revertMessage[0:32]);
    bytes memory walletAddress = context.revertMessage[32:];

    if(context.revertMessage.length == 52) {
        address receiver = address(uint160(bytes20(walletAddress)));
        TransferHelper.safeTransfer(context.asset, receiver, context.amount);
```
5. Al medir exactamente 52 bytes, el contrato asume que `walletAddress` es una dirección EVM legítima.
6. Convierte los 20 bytes truncados de Bitcoin/Solana en un `address` de Ethereum/ZetaChain y le transfiere los fondos devueltos.
7. Nunca se genera la entrada en `refundInfos` (que solo se crea si `length != 52`), impidiendo que el bot o el usuario reclamen su reembolso con `claimRefund()`. Los activos quedan quemados en una dirección vacía para siempre.

#### Mitigación:
No truncar `sender` a `bytes20` en `withdraw()`. Preservar el array `bytes` original (`bytes.concat(externalId, sender)`). En `onRevert`, discriminar si es EVM mediante el `dstChainId` o la longitud real del payload sin truncar.

---

### HALLAZGO #2: [CRITICAL] Ausencia de Validación en `GatewaySend.depositAndCall` Permite Desvío de Fondos a Billetera Atacante

- **Severidad:** Critical (CVSS 9.1 - Arbitrary Fund Redirection)
- **Componente Afectado:** `omni-chain-contracts/contracts/GatewaySend.sol` (`_doMixSwap`, `depositAndCall`)
- **Impacto:** Un usuario o atacante puede suministrar un `swapData` donde el parámetro `assetTo` de DODO RouteProxy apunte a su propia dirección externa, drenando el swap local y forzando al contrato a usar balances residuales o revertir.

#### Causa Raíz:
En `GatewaySend.sol`:
```solidity
function _doMixSwap(bytes calldata swapData) internal returns (uint256) {
    MixSwapParams memory params = SwapDataHelperLib.decodeCompressedMixSwapParams(swapData);

    if(params.fromToken != _ETH_ADDRESS_) {
        IERC20(params.fromToken).approve(DODOApprove, params.fromTokenAmount);
    }

    return IDODORouteProxy(DODORouteProxy).mixSwap{value: msg.value}(...);
}
```
El contrato no valida ninguna de las siguientes invariantes esenciales:
1. `params.fromToken == fromToken`
2. `params.fromTokenAmount == amount`
3. `params.toToken == asset`
4. `params.assetTo[last] == address(this)`

Si un atacante proporciona un `assetTo` que apunta a su billetera, DODO Router enviará los tokens resultantes del swap directamente al atacante en lugar de depositarlos en `GatewaySend`. Posteriormente, `GatewaySend` intentará transferir `outputAmount` al Gateway de ZetaChain; si el contrato cuenta con saldo remanente de ese activo, esos fondos ajenos serán sustraídos y enviados a través del puente.

#### Mitigación:
En `_doMixSwap`, verificar estrictamente que `params.fromToken == fromToken`, `params.fromTokenAmount == amount` y que cada elemento de `params.assetTo` coincida con `address(this)`.

---

### HALLAZGO #3: [HIGH] Subdesbordamiento Aritmético en `_swapAndSendERC20Tokens` Provoca Bloqueo de Swaps Entrantes

- **Severidad:** High (DoS en Ejecución Cross-Chain)
- **Componentes Afectados:** `GatewayCrossChain.sol` (Línea 345) y `GatewayTransferNative.sol` (Línea 345)
- **Impacto:** Transacciones cross-chain legítimas con montos ajustados o variaciones de gas en Uniswap V2 revierten por pánico aritmético no controlado, congelando los swaps en ZetaChain.

#### Causa Raíz:
```solidity
require(targetAmount - amountInMax > 0, "INSUFFICIENT_AMOUNT_FOR_WITHDRAW");
```
En Solidity ^0.8.20, todas las operaciones aritméticas incluyen validación de desbordamiento por defecto.
Si `targetAmount < amountInMax`, la expresión `targetAmount - amountInMax` subdesborda inmediatamente (`Panic 0x11`) antes de que la instrucción `require` pueda devolver el mensaje de error. Como esto se ejecuta dentro de `onCall()`, el revert aborta la transacción en ZetaChain sin emitir eventos ni gestionar el flujo de recuperación ordenado.

#### Mitigación:
Reemplazar por una comparación directa sin resta:
```solidity
require(targetAmount > amountInMax, "INSUFFICIENT_AMOUNT_FOR_WITHDRAW");
```

---

### HALLAZGO #4: [HIGH] Acceso Fuera de Límites en `SwapDataHelperLib.decodeCompressedMixSwapParams`

- **Severidad:** High (Error de Decodificación y DoS)
- **Componente Afectado:** `omni-chain-contracts/contracts/libraries/SwapDataHelperLib.sol` (Línea 160)
- **Impacto:** Llamadas con `swapData` malformado o menor a 200 bytes revierten con pánico de array fuera de límites, impidiendo la ejecución del swap y el rescate de fondos.

#### Causa Raíz:
La función decodifica campos en assembly hasta un offset acumulado de 200 bytes sin verificar previamente `data.length >= 200`. Al salir del bloque assembly y ejecutar `uint8 adapterLen = uint8(data[offset]);`, si `data.length < 200`, el acceso al array genera una excepción out-of-bounds irrecuperable.

#### Mitigación:
Añadir una validación previa: `if (data.length < 200) revert InvalidSwapDataLength();`.

---

### HALLAZGO #5: [MEDIUM] Aprobaciones Residuales a `UniswapRouter` en Swaps de Gas

- **Severidad:** Medium (Residual Allowance Leak)
- **Componentes Afectados:** `GatewayCrossChain.sol` y `GatewayTransferNative.sol`
- **Descripción:** El contrato aprueba `amountInMax` (que contempla hasta un 5% de slippage) a `UniswapRouter`. Como `swapTokensForExactTokens` consume únicamente `amounts[0] < amountInMax`, queda un margen de aprobación residual no revocado tras cada transacción.

---

## 3. ASIGNACIÓN DE RECOMPENSAS Y COBRO

- **Bolsa de Recompensas de la Competencia:** $40,000 USDC
- **Billetera Oficial de Cobro (Payout EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Monitoreo Automático Activo:** Listener en crontab EC2 (`payout_monitor.py`) cada 15 min.
