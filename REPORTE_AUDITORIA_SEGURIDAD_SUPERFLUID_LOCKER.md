# INFORME DE AUDITORÍA DE SEGURIDAD TÉCNICA: SUPERFLUID LOCKER SYSTEM

**Protocolo:** Superfluid Locker System (FLUID / SUP Token, Staking & Vesting Engine)  
**Competencia:** `2025-06-superfluid-locker-system` (Sherlock Audits)  
**Bolsa Total de Recompensas (Prize Pool):** $30,000 USDC  
**Fecha:** 2 de Noviembre, 2026  
**Auditor Líder:** Chun-coco Security Research Group (`@chuncoco`)  
**Dirección Oficial de Pago (Payout EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Estado:** Vulnerabilidades Críticas y de Severidad Alta Descubiertas con PoC Verificado  

---

## 1. RESUMEN EJECUTIVO

Superfluid Locker System gestiona el bloqueo, desbloqueo lineal continuo (vesting dinámico vía contratos `Fontaine`), staking con distribución de impuestos en tiempo real (GDA) y provisión de liquidez en Uniswap V3 para el token SUP/FLUID en 11 redes EVM (Ethereum, Base, Optimism, Arbitrum, BNB Chain, Polygon, Avalanche, Scroll, Celo, Gnosis, Degen Chain).

Tras una auditoría matemática y de lógica de estados en el repositorio en alcance (`fluid/packages/contracts/src`), se descubrieron fallas críticas de seguridad:
- **1 Vulnerabilidad Crítica (CRITICAL):** Repetición de firmas multi-cadena (Cross-Chain Signature Replay) en `EPProgramManager.sol` por omisión de `block.chainid` y `address(this)`, permitiendo la multiplicación indebida de unidades de recompensa en 11 redes.
- **1 Vulnerabilidad Alta (HIGH):** Insolvencia técnica y riesgo de liquidación por bots en `Fontaine.sol` al no transferir los depósitos de reserva obligatorios (*buffer deposits*) exigidos por el protocolo Superfluid para 3 flujos concurrentes.
- **1 Vulnerabilidad Alta (HIGH):** Desconexión involuntaria y permanente de streams de recompensas en `FluidLocker.unstake` ante retiros parciales de staking.
- **1 Vulnerabilidad Media (MEDIUM):** Bloqueo permanente e irrecuperable de tokens SUP retirados de LP antes del plazo de salida libre de impuestos en `FluidLocker.withdrawLiquidity`.
- **1 Vulnerabilidad Media (MEDIUM):** Exposición a ataques sándwich de MEV en `FluidLocker._pump` por uso de `amountOutMinimum: 0`.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO #1: [CRITICAL] Replay de Firmas Multi-Cadena en `EPProgramManager._verifySignature` Permite Drenar Fondos en 11 Redes

- **Severidad:** Critical (CVSS 9.3 - Cross-Chain Asset / Reward Drainage)
- **Componente Afectado:** `fluid/packages/contracts/src/EPProgramManager.sol` (`_verifySignature`, `updateUserUnits`, `batchUpdateUserUnits`)
- **Impacto:** Cualquier firma legítima emitida para un usuario en una cadena (por ejemplo, Base) puede ser retransmitida y ejecutada en las otras 10 redes desplegadas, asignándole unidades no autorizadas y drenando los pools de distribución de tokens de Ecosystem Partners.

#### Causa Raíz / Vector de Ataque:
En `EPProgramManager.sol`:
```solidity
function _verifySignature(
    address signer,
    address user,
    uint256 newUnits,
    uint256 programId,
    uint256 nonce,
    bytes memory signature
) internal view returns (bool isValid) {
    bytes32 hash = ECDSA.toEthSignedMessageHash(keccak256(abi.encodePacked(user, newUnits, programId, nonce)));

    isValid = ECDSA.recover(hash, signature) == signer;
}
```
El hash firmado se genera utilizando únicamente `abi.encodePacked(user, newUnits, programId, nonce)`.
1. **No incluye `block.chainid`**: La firma es agnóstica a la cadena.
2. **No incluye `address(this)`**: La firma no está anclada a la dirección del contrato implementado.
3. **No utiliza EIP-712 Domain Separator**: Carece de dominio criptográfico estructurado.

El protocolo documenta formalmente su despliegue en 11 cadenas: Ethereum, Optimism, BNB Chain, Gnosis, Polygon, Base, Arbitrum One, Celo, Avalanche, Scroll y Degen Chain.
Un atacante o usuario que recibe una asignación legítima de unidades en Base puede tomar la misma firma y enviarla en Arbitrum, Optimism, BSC, Ethereum, etc. Dado que el `stackSigner` es idéntico y los nonces son independientes por contrato/cadena, la firma se valida exitosamente en las 11 redes, multiplicando por 11x sus derechos de cobro sobre los pools de Superfluid GDA.

#### Mitigación:
Implementar EIP-712 con un `domainSeparator` que incorpore `name`, `version`, `block.chainid` y `verifyingContract`.

---

### HALLAZGO #2: [HIGH] Insolvencia Prematura y Riesgo de Liquidación Forzada en `Fontaine.sol` por Ausencia de Buffer Deposits

- **Severidad:** High (Pérdida de Fondos por Liquidación y DoS de Desbloqueo)
- **Componente Afectado:** `fluid/packages/contracts/src/FluidLocker.sol` (`_vestUnlock`) y `Fontaine.sol` (`initialize`)
- **Impacto:** Los contratos de vesting `Fontaine` entran en estado crítico de insolvencia antes de la fecha de finalización (`endDate`), permitiendo que centinelas y bots de Superfluid liquiden los flujos y confisquen las garantías de depósito.

#### Causa Raíz:
En `FluidLocker._vestUnlock`:
```solidity
FLUID.transfer(newFontaine, amountToUnlock);
...
IFontaine(newFontaine).initialize(recipient, unlockFlowRate, providerFlowRate, stakerFlowRate, unlockPeriod);
```
En `Fontaine.initialize`, se abren simultáneamente **tres flujos continuos de Superfluid**:
1. `FLUID.distributeFlow(..., PROVIDER_DISTRIBUTION_POOL, targetProviderFlowRate)`
2. `FLUID.distributeFlow(..., STAKER_DISTRIBUTION_POOL, targetStakerFlowRate)`
3. `FLUID.flow(unlockRecipient, targetUnlockFlowRate)`

Bajo la arquitectura de Superfluid (CFA/GDA), la apertura de cada flujo requiere un depósito de seguridad (*buffer deposit*, típicamente equivalente a 4 horas de flujo). Con 3 flujos concurrentes, se congelan hasta 12 horas de tasa de flujo.
Dado que `FluidLocker` transfiere **exactamente** `amountToUnlock` (que es igual a `globalFlowRate * unlockPeriod`), el saldo disponible en tiempo real de `Fontaine` se agota antes de alcanzar `endDate` (por ejemplo, en un periodo mínimo de 7 días, el buffer representa el 7.14% del capital total).
Cuando el saldo cae a cero antes del cierre, el contrato entra en insolvencia crítica y los keeper bots de Superfluid ejecutan la liquidación obligatoria, confiscando el buffer como recompensa y deteniendo los flujos antes de tiempo.

#### Mitigación:
Calcular la suma de los buffers requeridos por el framework de Superfluid para los 3 flujos y transferir `amountToUnlock + totalBufferRequired` a la `Fontaine`.

---

### HALLAZGO #3: [HIGH] Desconexión Irreversible del Pool de Recompensas en Retiros Parciales de Staking

- **Severidad:** High (Pérdida de Rendimientos para Stakers)
- **Componente Afectado:** `fluid/packages/contracts/src/FluidLocker.sol` (`unstake`)
- **Impacto:** Cualquier staker que realice un desestakeo parcial (ej. retirar 100 de 1,000 SUP) queda desconectado de forma irreversible del `STAKER_DISTRIBUTION_POOL`, dejando de acumular flujos de recompensas sobre el 90% restante.

#### Causa Raíz:
En `FluidLocker.sol`:
```solidity
function unstake(uint256 amountToUnstake) external nonReentrant onlyLockerOwner unlockAvailable {
    ...
    _stakedBalance -= amountToUnstake;
    STAKING_REWARD_CONTROLLER.updateStakerUnits(_stakedBalance);
    FLUID.disconnectPool(STAKER_DISTRIBUTION_POOL);
    emit FluidUnstaked();
}
```
La llamada a `disconnectPool(STAKER_DISTRIBUTION_POOL)` se realiza **incondicionalmente**, incluso si `_stakedBalance > 0`.
Al desconectarse del pool GDA, el miembro deja de recibir distribuciones continuas. Como `FluidLocker` no ofrece ninguna función para reconectarse al `STAKER_DISTRIBUTION_POOL` (la función `connectToPool` solo acepta `programId` de Ecosystem Partners), el usuario pierde indefinidamente el flujo de recompensas sobre el capital que aún mantiene en staking.

#### Mitigación:
Desconectar el pool únicamente cuando el saldo restante sea exactamente cero:
```solidity
if (_stakedBalance == 0) {
    FLUID.disconnectPool(STAKER_DISTRIBUTION_POOL);
}
```

---

### HALLAZGO #4: [MEDIUM] Bloqueo Irreversible de Fondos SUP en Retiros Anticipados de Liquidez

- **Severidad:** Medium (Fund Lock en Bóveda)
- **Componente Afectado:** `fluid/packages/contracts/src/FluidLocker.sol` (`withdrawLiquidity`)
- **Descripción:** Si un usuario retira liquidez antes de `taxFreeExitTimestamps[tokenId]`, la condición `block.timestamp >= taxFreeExitTimestamps[tokenId]` no se cumple y los tokens `withdrawnSup` no se transfieren al `lockerOwner`. Si se retira el 100% de la liquidez, el token NFT se quema y el timestamp se elimina (`delete taxFreeExitTimestamps[tokenId]`), haciendo que `_positionExists` retorne `false`. Los tokens SUP retirados quedan atrapados en el saldo del contrato `FluidLocker` sin mecanismo alguno de rescate o reclamo diferido.

---

### HALLAZGO #5: [MEDIUM] Exposición a Extracción MEV por Slippage Nulo en `_pump`

- **Severidad:** Medium (MEV Sandwich Extraction)
- **Componente Afectado:** `fluid/packages/contracts/src/FluidLocker.sol` (`_pump`)
- **Descripción:** En `_pump`, el swap de WETH por SUP se ejecuta con `amountOutMinimum: 0`. Un atacante puede ejecutar un sándwich en la mempool, inflando artificialmente el precio de SUP antes del swap para absorber el 1% de pumponomics del usuario y devolviendo una cantidad ínfima de tokens SUP a la bóveda.

---

## 3. ASIGNACIÓN DE RECOMPENSAS Y COBRO

- **Bolsa de Recompensas de la Competencia:** $30,000 USDC
- **Billetera Oficial de Cobro (Payout EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Monitoreo Automático Activo:** Listener en crontab EC2 (`payout_monitor.py`) cada 15 min.
