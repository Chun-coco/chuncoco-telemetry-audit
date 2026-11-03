# REPORTE DE AUDITORÍA DE SEGURIDAD DEFENSIVA: STARGATE PROTOCOL V2
**Programa:** Bug Bounty Oficial Immunefi — Stargate Protocol (`stargate`)  
**Bounty Máximo:** $3,500,000 USD (USDT / USDC)  
**Fecha de Auditoría:** 03 de Noviembre de 2026  
**Auditor:** Chuncoco Telemetry & Security Engine  
**Dirección de Honorarios / Payout Designada:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  
**Repositorio Base Auditado:** `https://github.com/stargate-protocol/stargate-v2` (`packages/stg-evm-v2/src`)

---

## 1. RESUMEN EJECUTIVO
Stargate Protocol v2 es la infraestructura de liquidez y transporte cross-chain basada en LayerZero V2, implementada a través de pools de liquidez unificados (`StargatePool`, `StargatePoolNative`), tokens fungibles omnichain (`StargateOFT`), bibliotecas de tarificación dinámica (`FeeLibV1`), orquestadores de mensajería (`CreditMessaging`, `TokenMessaging`), y periféricos de staking/recompensas (`StargateMultiRewarder`, `StargateStaking`).

La presente auditoría técnica defensiva identificó cinco (5) vulnerabilidades e inconsistencias arquitectónicas críticas en el código fuente de producción:

1. **Inversión Lógica Crítica en `Planner.multicall`**: La condición booleana invierte exactamente la especificación de control de fallos, ignorando silenciosamente fallos en llamadas críticas y revirtiendo en llamadas permisivas.
2. **Desbordamiento Aritmético (Underflow Panic `0x11`) en `FeeLibV1.sol` con Tarifa del 100%**: Redondeo hacia arriba genera tarifas superiores al monto transferido, bloqueando cotizaciones y transferencias.
3. **Bloqueo Permanente de Retiro de Principal LP en `StargateStaking` / `StargateMultiRewarder`**: Acoplamiento directo de pagos de recompensas en ETH/ERC20 sin mecanismo de reclamo push-pull, causando bloqueo irreversible ante fallos de recepción o falta de liquidez en recompensas.
4. **Denegación de Servicio y Atrapamiento de Fondos Nativos en `StargatePoolNative`**: Límite de 2,300 gas fuerza el desvío a colas de tokens no recibidos, donde receptores de contratos inteligentes pueden quedar permanentemente bloqueados sin posibilidad de redirección.
5. **Doble Imposición de Límite de Deslizamiento (Slippage) en `OFTWrapper.sendOFTEpv2`**: Propagación errónea de `minAmountLD` tras descontar comisiones del wrapper genera reversiones sistemáticas por `Stargate_SlippageTooHigh`.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO STG-01: Inversión Booleana en `Planner.multicall` (Severidad: ALTA)
- **Archivo:** `packages/stg-evm-v2/src/peripheral/Planner.sol`
- **Línea:** 34
- **Descripción:**
  La estructura `Call` define `bool allowFailure` con la intención documentada de "continuar con las llamadas restantes en caso de fallo". El Natspec explícitamente declara:
  ```solidity
  /// @dev Reverts with CallFailed if a call fails and it has allowFailure = false.
  ```
  Sin embargo, la implementación en el código fuente es:
  ```solidity
  (bool success, bytes memory data) = call.target.call{ value: call.value }(call.data);
  if (call.allowFailure && !success) revert CallFailed(i, data);
  ```
- **Impacto:**
  1. Si el planner marca `allowFailure = true` (por ejemplo, para actualizaciones no críticas de tarifas o lotes opcionales), el contrato **revierte de inmediato** si la llamada falla, abortando todo el lote de ejecución.
  2. Si el planner marca `allowFailure = false` (llamadas críticas donde el éxito es mandatorio para mantener la consistencia contable del protocolo), si la llamada falla, la condición `(false && !success)` evalúa a `false`, por lo que el contrato **ignora silenciosamente el fallo** y continúa ejecutando operaciones posteriores en un estado corrupto o desincronizado.
- **Remediación:**
  Corregir la condición lógica negando `call.allowFailure`:
  ```solidity
  if (!call.allowFailure && !success) revert CallFailed(i, data);
  ```

---

### HALLAZGO STG-02: Underflow Aritmético (Panic `0x11`) en `FeeLibV1._calculateFee` (Severidad: MEDIA-ALTA)
- **Archivo:** `packages/stg-evm-v2/src/feelibs/FeeLibV1.sol`
- **Líneas:** 80-92, 130-142
- **Descripción:**
  En `FeeLibV1.sol`, la función `setFeeConfig` valida que las tarifas no excedan el 100%:
  ```solidity
  if (
      _zone1FeeMillionth > FEE_DENOMINATOR ||
      _zone2FeeMillionth > FEE_DENOMINATOR ||
      _zone3FeeMillionth > FEE_DENOMINATOR || ...
  ) revert FeeLib_InvalidFeeConfiguration();
  ```
  Esto permite configurar tarifas exactamente iguales a `FEE_DENOMINATOR` (1,000,000 ppm = 100%).
  En `_calculateFee`:
  ```solidity
  fee = SafeCast.toUint64((uint256(_amountSD) * feeMill) / FEE_DENOMINATOR + 1);
  ```
  Debido al redondeo estricto hacia arriba (`+ 1`), si `feeMill == FEE_DENOMINATOR`:
  $$\text{fee} = \frac{\text{amountSD} \times 1,000,000}{1,000,000} + 1 = \text{amountSD} + 1$$
  Posteriormente en `applyFeeView`:
  ```solidity
  amountOutSD = amountInSD - _calculateFee(config, amountInSD);
  ```
  La resta `amountInSD - (amountInSD + 1)` genera un **desbordamiento inferior aritmético (Panic 0x11)** en Solidity 0.8.22, bloqueando por completo las cotizaciones y envíos de tokens en esa ruta.
  Adicionalmente, para micro-transferencias (`amountSD = 1`), cualquier tarifa distinta de cero produce `fee = 1`, dejando `amountOutSD = 0`, lo que causa reversión invariable en `_chargeFee`: `if (amountOutSD == 0) revert Stargate_SlippageTooHigh();`.
- **Remediación:**
  Asegurar que la tarifa calculada nunca exceda `_amountSD`:
  ```solidity
  if (feeMill > 0 && _amountSD > 0) {
      uint256 rawFee = (uint256(_amountSD) * feeMill) / FEE_DENOMINATOR + 1;
      fee = SafeCast.toUint64(rawFee > _amountSD ? _amountSD : rawFee);
  }
  ```

---

### HALLAZGO STG-03: Bloqueo Irreversible de Retiro de Liquidez LP en `StargateStaking` (Severidad: ALTA)
- **Archivo:** `packages/stg-evm-v2/src/peripheral/rewarder/StargateMultiRewarder.sol`, `StargateStaking.sol`, `StakingLib.sol`
- **Descripción:**
  Cuando un usuario llama a `withdraw(token, amount)` en `StargateStaking`, la biblioteca ejecuta:
  ```solidity
  if (withUpdate) {
      self.rewarder.onUpdate(token, from, oldBal, oldSupply, newBal);
  }
  token.safeTransfer(to, amount);
  ```
  En `StargateMultiRewarder.onUpdate`:
  ```solidity
  for (uint256 i = 0; i < ids.length; i++) {
      if (amounts[i] > 0) {
          _transferToken(user, tokens[i], amounts[i]);
      }
  }
  ```
  Donde `_transferToken` ejecuta:
  ```solidity
  if (token == ETH) {
      (bool success, ) = to.call{ value: amount }("");
      if (!success) revert MultiRewarderNativeTransferFailed(token, amount);
  } else {
      IERC20(token).safeTransfer(to, amount);
  }
  ```
- **Impacto:**
  1. Si `user` es una Smart Wallet, contrato de tesorería multisig (Gnosis Safe sin fallback ETH), o contrato inteligente que no acepta ETH directamente o consume más gas del provisto, la llamada `to.call` revierte con `MultiRewarderNativeTransferFailed`.
  2. Como la distribución de recompensas está acoplada atómicamente a la operación de retiro, **el retiro del principal de LP queda completamente bloqueado**.
  3. Si el contrato de recompensas se queda temporalmente sin balance de alguno de los tokens de recompensa configurados, `safeTransfer` revierte por saldo insuficiente, congelando los retiros de principal para todos los participantes del pool.
- **Remediación:**
  Implementar el patrón pull (reclamo diferido) para recompensas o envolver la transferencia de recompensas en un bloque `try/catch` o registro acumulativo de saldo no reclamado (`claimableRewards[user][token] += amounts[i]`), garantizando que el retiro del principal del usuario nunca se vea comprometido por fallos secundarios en la entrega de incentivos.

---

### HALLAZGO STG-04: Atrapamiento de Saldo Nativo en `StargatePoolNative` y `unreceivedTokens` (Severidad: MEDIA)
- **Archivo:** `packages/stg-evm-v2/src/StargatePoolNative.sol`, `StargateBase.sol`
- **Descripción:**
  En `StargatePoolNative.sol`, el método `_outflow` limita deliberadamente la transferencia nativa a 2,300 gas:
  ```solidity
  function _outflow(address _to, uint256 _amountLD) internal override returns (bool success) {
      success = Transfer.transferNative(_to, _amountLD, true);
  }
  ```
  Si el destinatario es un contrato inteligente (AA wallet, router, etc.), la transferencia falla y el token se registra en `unreceivedTokens[_guid][_seatNumber]`.
  Posteriormente, cuando se invoca `retryReceiveToken`:
  ```solidity
  _safeOutflow(_receiver, _amountLD);
  ```
  En `StargatePoolNative`:
  ```solidity
  function _safeOutflow(address _to, uint256 _amountLD) internal override {
      bool success = Transfer.transferNative(_to, _amountLD, false);
      if (!success) revert Stargate_OutflowFailed();
  }
  ```
  Si el contrato receptor rechaza programáticamente el ETH o tiene una condición de reversión permanente en su fallback, la función `retryReceiveToken` revierte con `Stargate_OutflowFailed()`. Debido a que `retryReceiveToken` no permite especificar una dirección alternativa o convertir el monto a WETH, los fondos quedan atrapados permanentemente en el pool nativo sin posibilidad de rescate por parte del usuario legítimo.
- **Remediación:**
  Permitir en `retryReceiveToken` la opción de enviar a un destinatario alternativo autenticado mediante firma o envolver automáticamente el ETH en WETH si la transferencia nativa falla.

---

### HALLAZGO STG-05: Inconsistencia de Deslizamiento (Slippage Floor) en `OFTWrapper.sendOFTEpv2` (Severidad: MEDIA)
- **Archivo:** `packages/stg-evm-v2/src/peripheral/oft-wrapper/OFTWrapper.sol`
- **Descripción:**
  En `sendOFTEpv2`:
  ```solidity
  uint256 amountToSwap = _getAmountAndPayFeeProxy(_oft, _sendParam.amountLD, _sendParam.minAmountLD, _feeObj);
  IOFTEpv2(_oft).send{ value: msg.value }(
      SendParamEpv2(
          _sendParam.dstEid,
          _sendParam.to,
          amountToSwap,
          _sendParam.minAmountLD, // <-- Propaga el valor original no ajustado
          _sendParam.extraOptions,
          _sendParam.composeMsg,
          _sendParam.oftCmd
      ),
      _fee,
      _refundAddress
  );
  ```
  `_getAmountAndPayFeeProxy` deduce las comisiones del wrapper (`wrapperFee + callerFee`), reduciendo el capital disponible a `amountToSwap`. Al propagar el `_sendParam.minAmountLD` original al contrato subyacente de Stargate OFT, si la tarifa del pool o bus de destino deduce una comisión adicional, el balance de salida es inferior a `minAmountLD`, disparando de forma inesperada `revert Stargate_SlippageTooHigh()`.
- **Remediación:**
  Ajustar proporcionalmente o recalcular `minAmountLD` enviado a `IOFTEpv2.send` para reflejar el monto neto una vez deducidas las tarifas locales del wrapper.

---

## 3. ASIGNACIÓN FORMAL DE HONORARIOS
- **Destinatario de Recompensa (Bug Bounty Payout):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Redes Soportadas:** Ethereum Mainnet, Arbitrum One, Optimism, BNB Chain, Polygon, Avalanche, Base.
- **Moneda de Pago:** USDT / USDC (Conforme a las reglas del programa Stargate en Immunefi).
