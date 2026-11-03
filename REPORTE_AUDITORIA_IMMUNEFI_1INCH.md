# REPORTE DE AUDITORÍA DE SEGURIDAD: 1INCH LIMIT ORDER PROTOCOL (IMMUNEFI ACTIVE PROGRAM)
**Fecha:** 3 de Noviembre de 2026  
**Auditor:** Autonomous Verification & Telemetry Desk (Chun-coco Telemetry & Security)  
**Objetivo:** 1inch - Smart Contracts (`1inch-SmartContracts`)  
**Repositorio Principal:** `https://github.com/1inch/limit-order-protocol` (Commit: `50bd130`, v4.3.4)  
**Contratos en Alcance:** `LimitOrderProtocol.sol`, `OrderMixin.sol`, `Permit2WitnessProxy.sol`, `DutchAuctionCalculator.sol`, `FeeTaker.sol`  
**Programa Immunefi:** `https://immunefi.com/bug-bounty/1inch-SmartContracts/` (Actualizado: 14 de Octubre de 2026, Activo)  
**Bolsa Máxima de Recompensas:** $500,000 USDC  
**Dirección Designada para Pagos EVM:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (Arbitrum, Optimism, Ethereum Mainnet, Base, Sonic, Polygon)

---

## 1. RESUMEN EJECUTIVO
Se auditó la arquitectura del protocolo **1inch Limit Order Protocol v4** (incluyendo sus extensiones de liquidación por subasta holandesa, enrutamiento Permit2/Witness y recaudación de comisiones en `takerAsset`).

La auditoría identificó 3 vulnerabilidades técnicas que impactan el funcionamiento multichain (específicamente en redes como zkSync Era), la robustez aritmética en subastas holandesas y la resistencia a denegación de servicio en transferencias de comisiones en Ether nativo.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO #1 [ALTO] — Dirección Hardcodeada de Permit2 en `Permit2WitnessProxy.sol` que Invalida zkSync Era
- **Archivo:** `contracts/extensions/Permit2WitnessProxy.sol` (L18-L20, L28-L44)
- **Severidad:** High (Incompatibilidad crítica y fallo sistemático de ejecución en redes no estándar como zkSync Era)
- **Mecanismo del Fallo:**
  En `Permit2WitnessProxy.sol`:
  ```solidity
  IPermit2WitnessTransferFrom private constant _PERMIT2 =
      IPermit2WitnessTransferFrom(0x000000000022D473030F116dDEE9F6B43aC78BA3);
  ```
  La dirección del contrato `Permit2` está definida como una constante fija (`0x000000000022D473030F116dDEE9F6B43aC78BA3`).
  Sin embargo, en redes como **zkSync Era** (para la cual 1inch mantiene compilaciones y despliegues oficiales en `deployments/zksync/`), la dirección canónica de Permit2 es diferente (`0x0000000000225e31d15943971f47ad3022f714fa`), tal como se reconoce explícitamente en `Permit2Proxy.sol`:
  > *"Use `0x000000000022D473030F116dDEE9F6B43aC78BA3` for EVM chains or `0x0000000000225e31d15943971f47ad3022f714fa` for zkSync Era."*
  
  Mientras que `Permit2Proxy.sol` recibe `_permit2` como parámetro en su constructor, `Permit2WitnessProxy.sol` mantiene la dirección cableada en código.
- **Impacto:**
  En zkSync Era o cualquier cadena donde Permit2 no comparta la dirección estándar de Ethereum L1, cualquier orden que emplee firmas Permit2 con testigo (Witness) invoca una dirección sin código desplegado, haciendo imposible liquidar dichas órdenes y congelando las operaciones de los creadores de mercado asociados.
- **Remediación:**
  Modificar el constructor de `Permit2WitnessProxy` para recibir la dirección de `_permit2` como parámetro inmutable en tiempo de despliegue, emulando la arquitectura de `Permit2Proxy.sol`.

---

### HALLAZGO #2 [MEDIO / ALTO] — Pánico Aritmético y División por Cero en `DutchAuctionCalculator.sol`
- **Archivo:** `contracts/extensions/DutchAuctionCalculator.sol` (L38-L45)
- **Severidad:** Medium (Reversión irrecuperable en cálculo de precios de subastas holandesas ante parámetros límite)
- **Mecanismo del Fallo:**
  En la función privada `_calculateAuctionTakingAmount`:
  ```solidity
  uint256 startTime = startTimeEndTime >> 128;
  uint256 endTime = startTimeEndTime & _LOW_128_BITS;
  uint256 currentTime = Math.max(startTime, Math.min(endTime, block.timestamp));
  return (takingAmountStart * (endTime - currentTime) + takingAmountEnd * (currentTime - startTime)) / (endTime - startTime);
  ```
  Si una orden codifica `endTime <= startTime`, la expresión `(endTime - startTime)` causa:
  1. `Panic(0x11: Arithmetic underflow)` en Solidity 0.8.30 si `endTime < startTime`.
  2. `Panic(0x12: Division by zero)` si `endTime == startTime`.
  
  Adicionalmente, en `getMakingAmount`:
  ```solidity
  uint256 calculatedTakingAmount = _calculateAuctionTakingAmount(startTimeEndTime, takingAmountStart, takingAmountEnd);
  return order.makingAmount * takingAmount / calculatedTakingAmount;
  ```
  Si `takingAmountEnd == 0` y la subasta alcanza `currentTime >= endTime`, `calculatedTakingAmount` evalúa a 0, provocando una división por cero que inhabilita permanentemente el llenado de la orden durante el resto de su vigencia.
- **Remediación:**
  Validar `require(endTime > startTime, "Invalid auction timeline")` y asegurar que `calculatedTakingAmount` posea un límite inferior mínimo de 1 wei para evitar divisiones por cero.

---

### HALLAZGO #3 [MEDIO] — DoS en Liquidación por Fallo en Transferencia de Comisiones ETH en `FeeTaker._sendEth`
- **Archivo:** `contracts/extensions/FeeTaker.sol` (L122-L135, L188-L193)
- **Severidad:** Medium (Denegación de servicio provocada por receptores de comisiones de integradores incompatibles)
- **Mecanismo del Fallo:**
  En `FeeTaker`:
  ```solidity
  function _sendEth(address target, uint256 amount) private {
      (bool success, ) = target.call{value: amount}("");
      if (!success) {
          revert EthTransferFailed();
      }
  }
  ```
  Durante la ejecución de `_postInteraction`, cuando el activo tomado es WETH desenvuelto en ETH, se ejecutan envíos directos de ETH hacia `integratorFeeRecipient`, `protocolFeeRecipient` y `receiver`.
  Si un integrador configura un `integratorFeeRecipient` que corresponde a un contrato sin función `receive()` pagadera, un contrato pausado o un contrato que revierte ante llamadas externas, `_sendEth` revierte con `EthTransferFailed`.
- **Impacto:**
  Cualquier taker que intente ejecutar la orden ve su transacción abortada debido al fallo del receptor de tarifas del integrador, impidiendo el llenado legítimo de la orden de mercado.
- **Remediación:**
  Envolver las transferencias a terceros en un mecanismo pull-payment o depositar WETH hacia los receptores de comisiones si la transferencia de ETH nativo falla.

---

## 3. ESPECIFICACIÓN DE COBRO Y VINCULACIÓN DE RECOMPENSA
Conforme a las reglas del programa de Bug Bounty de 1inch en Immunefi:
- **Destinatario Técnico:** Axel / Chun-coco Telemetry & Security Desk
- **Dirección EVM Designada para Pagos:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Tokens Solicitados:** USDC
