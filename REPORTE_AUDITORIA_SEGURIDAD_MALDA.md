# REPORTE DE AUDITORÍA DE SEGURIDAD: MALDA PROTOCOL
**Target:** `2025-07-malda` (`malda-lending` & `malda-zk-coprocessor`)  
**Commit de Referencia:** `ab4fa9b2da94bc7f5b0e6d4c52f61e28b0820a54`  
**Fecha:** 2 de Noviembre de 2026  
**Auditor:** Chun-coco Autonomous Web3 Security Team  
**Dirección EVM de Cobro / Bounty:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`

---

## 1. RESUMEN EJECUTIVO

Malda Protocol implementa un protocolo de préstamos (*lending*) multichain asistido por un coprocesador ZK (RISC0) y un secuenciador centralizado. La arquitectura divide los mercados entre una cadena Host (ej. Linea / Ethereum) y múltiples cadenas Extension (Base, Arbitrum, Optimism), coordinando liquidez mediante puentes como Across y Everclear.

La presente auditoría identificó **5 vulnerabilidades críticas y altas** en los contratos de `malda-lending`:
1. **[CRÍTICO] Dilución Severa del Tipo de Cambio (*Exchange Rate*) por Omisión de `totalUnderlying` en `mTokenStorage.sol`:** La tasa de cambio usa `_getCashPrior()` (solo balance local de la cadena Host) mientras `totalSupply` se infla con depósitos de todas las extension chains, colapsando el valor de los shares y permitiendo arbitraje predatorio.
2. **[CRÍTICO] Falla Permanente en la Ejecución de Rebalanceo en `AcrossBridge.sol` por `depositor` Inválido:** Pasa `msg.sender` (`Rebalancer`) en lugar de `address(this)`, intentando que Across extraiga fondos de un contrato que ya no los posee ni tiene allowances concedidas.
3. **[ALTO] Bloqueo DoS Post-Expiración de Ventana por Variable en Memoria en `Rebalancer.sendMsg`:** Lectura de `transferInfo` en memoria previa al reseteo de la ventana temporal de 24 horas bloquea transferencias legítimas con `Rebalancer_TransferSizeExcedeed`.
4. **[ALTO] Reversión Sistemática de `wrapAndSupplyOnExtensionMarket` en `WrapAndSupply.sol`:** El contrato convierte el 100% de `msg.value` en WETH y envía 0 ETH a `mTokenGateway.supplyOnHost`, revirtiendo siempre que `gasFee > 0`.
5. **[ALTO] Desincronización de Decimales y Riesgo de División por Cero en `MixedPriceOracleV4.sol`:** `_absDiff` compara precios crudos de Api3 (18 decimales) y eOracle (8 decimales) sin normalizar, invalidando el cálculo de delta e induciendo DoS por `Panic(0x12)`.

---

## 2. HALLAZGOS DETALLADOS

### HALLAZGO #01: [CRÍTICO] Dilución Severa del Tipo de Cambio (*Exchange Rate*) por Omisión de `totalUnderlying` en `mTokenStorage.sol`

* **Contratos:** `mTokenStorage.sol` (L23-38), `mToken.sol` (L690-695), `mErc20Host.sol` (L434-455).
* **Severidad:** Crítica (Pérdida directa de fondos de usuarios / Manipulación de mercado).

#### Descripción Técnica
En un sistema de lending estilo Compound, la tasa de cambio determina cuántos activos subyacentes respalda cada `mToken`:
$$\text{ExchangeRate} = \frac{\text{TotalCash} + \text{TotalBorrows} - \text{TotalReserves}}{\text{TotalSupply}}$$

En Malda, los desarrolladores crearon una variable contable `totalUnderlying` en `mToken.sol` que se incrementa cada vez que un usuario suministra fondos en una cadena de extensión mediante `mintExternal`:
```solidity
// mToken.sol L692
totalUnderlying += actualMintAmount;
```
Sin embargo, en `mTokenStorage.sol`, la función `_exchangeRateStored()` fue codificada así:
```solidity
function _exchangeRateStored() internal view virtual returns (uint256) {
    uint256 _totalSupply = totalSupply;
    if (_totalSupply == 0) {
        return initialExchangeRateMantissa;
    } else {
        uint256 totalCash = _getCashPrior();
        uint256 cashPlusBorrowsMinusReserves = totalCash + totalBorrows - totalReserves;
        uint256 exchangeRate = (cashPlusBorrowsMinusReserves * expScale) / _totalSupply;
        return exchangeRate;
    }
}
```
Y en `mErc20.sol`:
```solidity
function _getCashPrior() internal view virtual override returns (uint256) {
    return IERC20(underlying).balanceOf(address(this));
}
```
`mErc20Host` NO sobreescribe `_getCashPrior()`. Por tanto, `totalCash` contabiliza únicamente los tokens ERC20 físicamente depositados en la cadena Host.

#### Impacto
Cuando los usuarios depositan liquidez en Arbitrum o Base a través del `mTokenGateway`:
1. `_mintExternal` en Host acuña `mTokens` a favor del usuario. `totalSupply` aumenta.
2. Los tokens físicos quedan en el gateway de Arbitrum/Base. El balance de la Host (`_getCashPrior()`) no aumenta.
3. El numerador de `_exchangeRateStored()` permanece constante mientras el denominador (`totalSupply`) se dispara.
4. **El tipo de cambio colapsa.** Los usuarios existentes ven su poder de retiro severamente mermado.
5. Un atacante puede depositar en Host a precio deprimido y, en cuanto el `Rebalancer` transporta liquidez a Host, el tipo de cambio salta bruscamente, permitiendo al atacante retirar una porción exorbitante de fondos del pool.

#### Prueba de Concepto (PoC)
```solidity
// Host Market inicial:
// Cash = 100,000 USDC, Borrows = 0, Reserves = 0, TotalSupply = 100,000 shares -> Rate = 1.0
// Usuario deposita 900,000 USDC en Arbitrum Gateway.
// Host ejecuta mintExternal:
// TotalSupply = 1,000,000 shares.
// Cash en Host sigue siendo 100,000 USDC.
// Nuevo ExchangeRate = 100,000 / 1,000,000 = 0.1 USDC por share!
// Los depositantes originales de 100,000 USDC ahora sólo pueden retirar 10,000 USDC! (90% pérdida).
```

#### Mitigación
Modificar `_exchangeRateStored()` en `mErc20Host` para utilizar `totalUnderlying` o el total de activos consolidados multichain:
```solidity
uint256 totalCash = totalUnderlying;
```

---

### HALLAZGO #02: [CRÍTICO] Falla Permanente en la Ejecución de Rebalanceo en `AcrossBridge.sol` por `depositor` Inválido

* **Contrato:** `rebalancer/bridges/AcrossBridge.sol` (L120-165).
* **Severidad:** Crítica (Incapacidad de rebalancear liquidez cross-chain / DoS estructural).

#### Descripción Técnica
En `AcrossBridge.sol`:
```solidity
function sendMsg(
    uint256 _extractedAmount,
    address _market,
    uint32 _dstChainId,
    address _token,
    bytes memory _message,
    bytes memory
) external payable onlyRebalancer {
    DecodedMessage memory msgData = _decodeMessage(_message);
    require(_extractedAmount == msgData.inputAmount, BaseBridge_AmountMismatch());
    require(whitelistedRelayers[_dstChainId][msgData.relayer], AcrossBridge_RelayerNotValid());

    // retrieve tokens from `Rebalancer`
    IERC20(_token).safeTransferFrom(msg.sender, address(this), msgData.inputAmount);
    ...
    _depositV3Now(_message, _token, _dstChainId, _market);
}

function _depositV3Now(bytes memory _message, address _token, uint32 _dstChainId, address _market) private {
    DecodedMessage memory msgData = _decodeMessage(_message);
    SafeApprove.safeApprove(_token, address(acrossSpokePool), msgData.inputAmount);
    IAcrossSpokePoolV3(acrossSpokePool).depositV3Now(
        msg.sender, // <-- ERROR: msg.sender es Rebalancer!
        address(this),
        _token,
        address(0),
        msgData.inputAmount,
        msgData.outputAmount,
        uint256(_dstChainId),
        msgData.relayer,
        msgData.deadline,
        msgData.exclusivityDeadline,
        abi.encode(_market)
    );
}
```

#### Impacto
1. En `sendMsg`, `AcrossBridge` ya transfirió los fondos de `msg.sender` (`Rebalancer`) hacia `address(this)` (`AcrossBridge`).
2. `AcrossBridge` otorga aprobación (`safeApprove`) a `acrossSpokePool` para gastar desde `address(this)`.
3. Al invocar `depositV3Now`, le pasa `depositor = msg.sender` (`Rebalancer`).
4. El contrato `SpokePool` de Across ejecuta `IERC20.safeTransferFrom(depositor, address(this), inputAmount)`.
5. Como `Rebalancer` ya no tiene los tokens en su balance y no ha aprobado a `acrossSpokePool`, la llamada **revierte indefectiblemente**. Ninguna orden de rebalanceo a través de Across puede completarse.

#### Mitigación
Cambiar el parámetro `depositor` por `address(this)`:
```solidity
IAcrossSpokePoolV3(acrossSpokePool).depositV3Now(
    address(this), // AcrossBridge es quien tiene los tokens y la aprobación
    address(this),
    ...
);
```

---

### HALLAZGO #03: [ALTO] Bloqueo DoS Post-Expiración de Ventana por Variable en Memoria en `Rebalancer.sendMsg`

* **Contrato:** `rebalancer/Rebalancer.sol` (L139-180).
* **Severidad:** Alta (Denegación de servicio en transferencias de liquidez).

#### Descripción Técnica
```solidity
TransferInfo memory transferInfo = currentTransferSize[_msg.dstChainId][_msg.token];
uint256 transferSizeDeadline = transferInfo.timestamp + transferTimeWindow;
if (transferSizeDeadline < block.timestamp) {
    currentTransferSize[_msg.dstChainId][_msg.token] = TransferInfo(_amount, block.timestamp);
} else {
    currentTransferSize[_msg.dstChainId][_msg.token].size += _amount;
}

uint256 _maxTransferSize = maxTransferSizes[_msg.dstChainId][_msg.token];
if (_maxTransferSize > 0) {
    require(transferInfo.size + _amount < _maxTransferSize, Rebalancer_TransferSizeExcedeed());
}
```

#### Impacto
La variable `transferInfo` se lee en memoria antes del `if`.
Si transcurrieron más de 24 horas (`transferTimeWindow = 86400`), la ventana debe reiniciarse. En almacenamiento (`storage`) se guarda `TransferInfo(_amount, block.timestamp)`.
Sin embargo, el `require` posterior evalúa `transferInfo.size + _amount < _maxTransferSize` usando la copia antigua en memoria. Si el periodo anterior había alcanzado el límite (ej. 95,000 / 100,000), cualquier transferencia posterior en el nuevo día revierte porque $95,000 + \text{amount} \ge 100,000$. El puente queda inoperativo hasta que se envíe una transferencia residual que logre pasar el check obsoleto.

#### Mitigación
Actualizar `transferInfo.size` en memoria cuando expire la ventana:
```solidity
if (transferSizeDeadline < block.timestamp) {
    currentTransferSize[_msg.dstChainId][_msg.token] = TransferInfo(_amount, block.timestamp);
    transferInfo.size = 0;
} else {
    currentTransferSize[_msg.dstChainId][_msg.token].size += _amount;
}
```

---

### HALLAZGO #04: [ALTO] Reversión Sistemática de `wrapAndSupplyOnExtensionMarket` en `WrapAndSupply.sol`

* **Contrato:** `utils/WrapAndSupply.sol` (L75-101), `mTokenGateway.sol` (L125-140).
* **Severidad:** Alta (Inutilidad total de la función de depósito nativo en cadenas de extensión).

#### Descripción Técnica
En `WrapAndSupply.sol`:
```solidity
function wrapAndSupplyOnExtensionMarket(address mTokenGateway, address receiver, bytes4 selector)
    external
    payable
{
    address underlying = ImTokenGateway(mTokenGateway).underlying();
    require(underlying == address(wrappedNative), WrapAndSupply_AddressNotValid());

    uint256 amount = _wrap();

    IERC20(underlying).approve(mTokenGateway, 0);
    IERC20(underlying).approve(mTokenGateway, amount);
    ImTokenGateway(mTokenGateway).supplyOnHost(amount, receiver, selector);
}

function _wrap() private returns (uint256) {
    uint256 amount = msg.value;
    require(amount > 0, WrapAndSupply_AmountNotValid());

    wrappedNative.deposit{value: amount}();
    return amount;
}
```
Y en `mTokenGateway.sol`:
```solidity
function supplyOnHost(uint256 amount, address receiver, bytes4 lineaSelector)
    external
    payable
    ...
{
    require(amount > 0, mTokenGateway_AmountNotValid());
    require(msg.value >= gasFee, mTokenGateway_NotEnoughGasFee());
```

#### Impacto
`_wrap()` deposita el 100% de `msg.value` en WNative. La llamada subsiguiente a `supplyOnHost` no envía ningún valor en ETH (`msg.value == 0`).
Siempre que el protocolo configure una tarifa de gas cross-chain (`gasFee > 0`), la llamada revierte de inmediato con `mTokenGateway_NotEnoughGasFee()`. No existe forma de que un usuario deposite ETH nativo en una cadena de extensión con este contrato.

#### Mitigación
Permitir al usuario especificar la porción destinada a `gasFee` y pasarla en la llamada a `supplyOnHost`:
```solidity
function wrapAndSupplyOnExtensionMarket(address mTokenGateway, address receiver, bytes4 selector)
    external
    payable
{
    uint256 fee = ImTokenGateway(mTokenGateway).gasFee();
    require(msg.value > fee, WrapAndSupply_AmountNotValid());
    uint256 amount = msg.value - fee;
    wrappedNative.deposit{value: amount}();

    IERC20(underlying).approve(mTokenGateway, amount);
    ImTokenGateway(mTokenGateway).supplyOnHost{value: fee}(amount, receiver, selector);
}
```

---

### HALLAZGO #05: [ALTO] Desincronización de Decimales y Riesgo de División por Cero en `MixedPriceOracleV4.sol`

* **Contrato:** `oracles/MixedPriceOracleV4.sol` (L130-167).
* **Severidad:** Alta (Oráculo corrupto y DoS en liquidaciones/préstamos).

#### Descripción Técnica
```solidity
(, int256 apiV3Price,, uint256 apiV3UpdatedAt,) = IDefaultAdapter(config.api3Feed).latestRoundData();
(, int256 eOraclePrice,, uint256 eOracleUpdatedAt,) = IDefaultAdapter(config.eOracleFeed).latestRoundData();

// check delta
uint256 delta = _absDiff(apiV3Price, eOraclePrice);
uint256 deltaBps = (delta * PRICE_DELTA_EXP) / uint256(eOraclePrice < 0 ? -eOraclePrice : eOraclePrice);
```

#### Impacto
1. Los feeds de Api3 y eOracle/Chainlink típicamente poseen diferentes resoluciones de decimales (18 vs 8). `_absDiff` calcula la diferencia absoluta entre números con escalas incomparables ($3 \times 10^{21}$ vs $3 \times 10^{11}$), arrojando siempre un `deltaBps` astronómico. Esto anula la validación de consenso de oráculos y fuerza permanentemente el uso de eOracle.
2. Si `eOraclePrice == 0` (por falla transitoria o inicialización), la división `(delta * PRICE_DELTA_EXP) / 0` produce un revert `Panic(0x12)`.
3. No existe verificación de que los precios devueltos sean estrictamente positivos antes del casteo.

#### Mitigación
Normalizar ambos precios a 18 decimales antes de computar `_absDiff` y validar que ambos sean mayores a cero:
```solidity
require(apiV3Price > 0 && eOraclePrice > 0, MixedPriceOracle_InvalidPrice());
uint256 normApi = uint256(apiV3Price) * 10**(18 - apiDecimals);
uint256 normEO = uint256(eOraclePrice) * 10**(18 - eoDecimals);
uint256 delta = normApi >= normEO ? normApi - normEO : normEO - normApi;
uint256 deltaBps = (delta * PRICE_DELTA_EXP) / normEO;
```

---

## 3. VERIFICACIÓN Y DEPÓSITO DE RECOMPENSAS

* **Dirección EVM de Recepción de Fondos / Recompensas:**  
  `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
  *(Válida en Arbitrum, Optimism, Ethereum, BSC y Polygon para USDC / USDT)*.
* **Repositorio de Telemetría:**  
  [`https://github.com/Chun-coco/chuncoco-telemetry-audit`](https://github.com/Chun-coco/chuncoco-telemetry-audit)
