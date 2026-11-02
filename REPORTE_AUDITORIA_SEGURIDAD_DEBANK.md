# REPORTE DE AUDITORÍA DE SEGURIDAD: DEBANK SWAP ROUTER V1
**Target:** `2025-07-debank` (`swap-router-v1`)  
**Commit de Referencia:** Sherlock Audit Competition `2025-07-debank`  
**Fecha:** 2 de Noviembre de 2026  
**Auditor:** Chun-coco Autonomous Web3 Security Team  
**Dirección EVM de Cobro / Bounty:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`

---

## 1. RESUMEN EJECUTIVO

DeBank Swap Router V1 implementa una infraestructura de enrutamiento y agregación de intercambios (*swaps*) descentralizados con soporte multi-path y múltiples DEX (Uniswap V2-V4, Curve V1-V2, Balancer, Velodrome, Maker PSM) y agregadores (1inch, Paraswap, Matcha, KyberSwap).

La presente auditoría identificó **4 vulnerabilidades Altas y Medias** en los contratos principales (`Router.sol`, `DexSwap.sol`, `Spender.sol`, `Executor.sol`, `UniversalERC20.sol` y ejecutores específicos):
1. **[ALTO] Estipendio de Gas Rígido de 2300 en `UniversalERC20.universalTransfer` Bloquea Swaps a Billeteras de Contrato Inteligente (EIP-1884):** Uso de `.transfer()` en lugar de `.call{value: ...}("")` revierte transacciones hacia Gnosis Safe, cuentas ERC-4337 o contratos receptores de comisiones.
2. **[ALTO] Ausencia de Protección de Deslizamiento en Saltos Intermedios (`min_amount = 0`) en Ejecutores de Curve y Uniswap V3:** Rutas multi-hop ejecutan saltos intermedios con tolerancia cero, permitiendo extracción de MEV por ataques sandwich.
3. **[MEDIO] Bloqueo Permanente e Irrecuperable de Activos Intermedios en `Executor.sol` por Ausencia de Funciones de Rescate:** Tokens residuales o intermedios quedan atrapados sin mecanismo de retiro administrativo.
4. **[MEDIO] Riesgo de Corrupción de Almacenamiento en `Spender.sol` por `ReentrancyGuard` en Adaptadores Ejecutados vía `delegatecall`:** Adaptadores modifican el slot 0 de `Spender` sin layout de almacenamiento reservado.

---

## 2. HALLAZGOS DETALLADOS

### HALLAZGO #01: [ALTO] Estipendio de Gas Rígido de 2300 en `UniversalERC20.universalTransfer` Bloquea Swaps a Billeteras de Contrato Inteligente (EIP-1884)

* **Contratos:** `library/UniversalERC20.sol` (L15-33), `router/Router.sol` (L100, L113), `aggregatorRouter/DexSwap.sol` (L291, L322).
* **Severidad:** Alta (Incompatibilidad crítica y DoS para contratos inteligentes / multisigs).

#### Descripción Técnica
En `UniversalERC20.sol`:
```solidity
function universalTransfer(IERC20 token, address payable to, uint256 amount) internal {
    if (amount > 0) {
        if (isETH(token)) {
            to.transfer(amount); // <-- 2300 gas limit!
        } else {
            token.safeTransfer(to, amount);
        }
    }
}
```
El método `to.transfer(amount)` limita la ejecución del receptor a 2300 unidades de gas.
Desde la implementación del EIP-1884 en Ethereum y redes compatibles (que incrementó el costo de lectura de almacenamiento `SLOAD`), 2300 de gas es insuficiente para contratos que emiten eventos, leen variables o actualizan balances.

#### Impacto
Cualquier usuario que opere desde una billetera de contrato inteligente (Gnosis Safe, Argent, cuentas abstractas ERC-4337) o cualquier protocolo que configure un `feeReceiver` basado en contrato sufrirá la reversión inmediata de la transacción con error `OutOfGas`.

#### Mitigación
Reemplazar `to.transfer(amount)` por una llamada de bajo nivel con propagación de errores:
```solidity
(bool success, ) = to.call{value: amount}("");
require(success, "ETH_TRANSFER_FAILED");
```

---

### HALLAZGO #02: [ALTO] Ausencia de Protección de Deslizamiento en Saltos Intermedios (`min_amount = 0`) en Ejecutores de Curve y Uniswap V3

* **Contratos:** `executor/curve/CurveV1Executor.sol` (L30-40), `executor/curve/CurveV2Executor.sol` (L77-101), `executor/uniswap/UniswapV3Executor.sol` (L67-78).
* **Severidad:** Alta (Pérdida por extracción MEV y arbitraje sandwich).

#### Descripción Técnica
En `CurveV1Executor.sol`:
```solidity
if (curveV1SwapType == 0) {
    ICurveV1Pool(pool).exchange(i, j, fromTokenAmount, 0); // min_amount = 0
} else if (curveV1SwapType == 1) {
    ICurveV1Pool(pool).exchange_underlying(i, j, fromTokenAmount, 0); // min_amount = 0
}
```
Y en `UniswapV3Executor.sol`:
```solidity
IUniswapV3Router(arg.router).exactInputSingle(
    IUniswapV3Router.ExactInputSingleParams02({
        tokenIn: fromToken,
        tokenOut: toToken,
        fee: arg.fee,
        recipient: address(this),
        amountIn: fromTokenAmount,
        amountOutMinimum: 0, // <-- Sin slippage intermedio!
        sqrtPriceLimitX96: ...
    })
);
```

#### Impacto
En intercambios con múltiples saltos (ej. Token A $\rightarrow$ Token B $\rightarrow$ Token C):
El primer salto se ejecuta con `amountOutMinimum = 0`. Un bot de arbitraje MEV puede alterar las reservas del pool intermedio (sandwich attack), extrayendo valor en el token intermedio B antes de que se ejecute el segundo salto. Aunque el router verifique el slippage final global, la ausencia de límites locales en los saltos intermedios maximiza la pérdida del usuario hasta el borde del límite de slippage configurado.

#### Mitigación
Permitir que el payload del swap (`payload` / `data`) incluya un parámetro de slippage mínimo por tramo calculado por el motor off-chain y validar que la salida intermedia cumpla dicho umbral.

---

### HALLAZGO #03: [MEDIO] Bloqueo Permanente e Irrecuperable de Activos Intermedios en `Executor.sol`

* **Contrato:** `executor/Executor.sol` (L420-515).
* **Severidad:** Media (Fondos atrapados permanentemente en el contrato).

#### Descripción Técnica
`Executor.sol` se despliega como contrato independiente propiedad del `Router`. Durante ejecuciones de `executeMegaSwap` y `executeMultiPath`, los fondos pasan por adaptadores vía `delegatecall`.
Si ocurre un desbalance, slippage residual o remanente en tokens intermediarios, estos quedan en el balance de `Executor`. El contrato carece de funciones de retiro de emergencia (`rescueToken`, `sweep`).

#### Mitigación
Incorporar una función protegida con `onlyOwner` en `Executor.sol`:
```solidity
function rescueToken(address token, address to, uint256 amount) external onlyOwner {
    IERC20(token).universalTransfer(payable(to), amount);
}
```

---

### HALLAZGO #04: [MEDIO] Riesgo de Corrupción de Almacenamiento en `Spender.sol` por `ReentrancyGuard` en Adaptadores

* **Contratos:** `aggregatorRouter/Spender.sol` (L345-389), `aggregatorRouter/adapter/UniAdapter.sol` (L20, L39), `aggregatorRouter/adapter/OneinchAdapter.sol` (L78, L97).
* **Severidad:** Media (Integridad de almacenamiento bajo `delegatecall`).

#### Descripción Técnica
`Spender.sol` ejecuta `_delegate(adapter, data)` donde el objetivo es un adaptador que hereda de `ReentrancyGuard`.
`ReentrancyGuard` de OpenZeppelin utiliza una variable privada de estado `_status` ubicada en el **slot 0** del contrato.
Dado que `Spender.sol` no define variables de estado antes de la llamada, la mutación de `_status` escribe directamente en el slot 0 de `Spender`. Si en futuras versiones o actualizaciones `Spender` define variables de almacenamiento, sus valores serán sobreescritos y corrompidos durante cualquier swap.

#### Mitigación
Remover `ReentrancyGuard` de los contratos de adaptadores que se invocan vía `delegatecall`, delegando la protección de reentrada exclusivamente al contrato invocador (`DexSwap.sol`).

---

## 3. VERIFICACIÓN Y ASIGNACIÓN DE RECOMPENSA

* **Dirección EVM de Depósito y Cobro (Binance Oficial):**  
  `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
  *(Acepta USDC y USDT en Arbitrum One, BNB Smart Chain, Polygon y Ethereum)*.
* **Repositorio Público de Telemetría:**  
  [`https://github.com/Chun-coco/chuncoco-telemetry-audit`](https://github.com/Chun-coco/chuncoco-telemetry-audit)
