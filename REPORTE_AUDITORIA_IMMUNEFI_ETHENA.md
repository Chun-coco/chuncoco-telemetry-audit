# REPORTE DE AUDITORÍA DE SEGURIDAD DEFENSIVA: ETHENA LABS (USDE & SUSDE)
**Programa:** Bug Bounty Oficial Immunefi — Ethena (`ethena`)  
**Bounty Máximo:** $3,000,000 USD (USDC)  
**Fecha de Auditoría:** 03 de Noviembre de 2026  
**Auditor:** Chuncoco Telemetry & Security Engine  
**Dirección de Honorarios / Payout Designada:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  
**Repositorio Base Auditado:** `https://github.com/ethena-labs/bbp-public-assets` (`contracts/contracts/`)

---

## 1. RESUMEN EJECUTIVO
Ethena es el protocolo emisor del dólar sintético USDe y su derivado de rendimiento sUSDe (`StakedUSDeV2`), respaldado por posiciones delta-neutrales y activos colaterales (ETH, WETH, LSTs) delegados a custodios institucionales (`EthenaMinting`).

La presente revisión de seguridad defensiva identificó cuatro (4) vectores de vulnerabilidad e inconsistencias operativas críticas en los contratos de producción:

1. **Truncamiento de Bits y Colisión de Nonces en `EthenaMinting.verifyNonce`**: El casteo `uint64(nonce) >> 8` descarta los 192 bits superiores del nonce de 256 bits, provocando colisiones entre órdenes válidas y permitiendo la invalidación prematura de órdenes firmadas legítimas.
2. **Reinicio Malicioso o Accidental de Periodo de Bloqueo en `StakedUSDeV2.cooldownAssets`**: La invocación de `cooldownAssets` o `cooldownShares` sobreescribe `cooldownEnd` sin mantener registros independientes, reiniciando el periodo completo de 90 días para todo el capital en espera del usuario.
3. **Pánico Aritmético por Desbordamiento Inferior en `StakedUSDe.totalAssets()`**: La resta `balanceOf - getUnvestedAmount()` carece de protección ante desbalances transitorios, disparando `Panic(0x11)` y paralizando todas las funciones del vault ERC-4626.
4. **Denegación de Servicio en Delegación de Custodia Nativa (`_transferEthCollateral`)**: Transferencias directas de ETH nativo a custodios que rechazan pagos directos sin calldata fuerzan la reversión atómica de las acuñaciones institucionales.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO ETH-01: Truncamiento de Bits de Nonce en `EthenaMinting.verifyNonce` (Severidad: ALTA)
- **Archivo:** `contracts/contracts/EthenaMinting.sol`
- **Líneas:** 443-451
- **Descripción:**
  La estructura `Order` define `uint256 nonce`. Sin embargo, en `verifyNonce`:
  ```solidity
  function verifyNonce(address sender, uint256 nonce) public view override returns (uint256, uint256, uint256) {
    if (nonce == 0) revert InvalidNonce();
    uint256 invalidatorSlot = uint64(nonce) >> 8;
    uint256 invalidatorBit = 1 << uint8(nonce);
    uint256 invalidator = _orderBitmaps[sender][invalidatorSlot];
    if (invalidator & invalidatorBit != 0) revert InvalidNonce();

    return (invalidatorSlot, invalidator, invalidatorBit);
  }
  ```
  Al realizar `uint64(nonce)`, los 192 bits más significativos del parámetro `uint256 nonce` se truncan a cero.
- **Impacto:**
  Cualquier par de órdenes firmadas cuyos nonces difieran únicamente en los bits 64..255 (por ejemplo, `nonce = 1` y `nonce = (1 << 64) + 1`) asignarán el mismo `invalidatorSlot` e `invalidatorBit`. Cuando la primera orden es procesada en `_deduplicateOrder`, el bit queda encendido. La segunda orden firmada por el usuario (o generada en una época distinta por un firmante delegado) será rechazada con `InvalidNonce()`, impidiendo la ejecución de órdenes institucionales legítimas y desestabilizando los motores de arbitraje.
- **Remediación:**
  Evitar el casteo restrictivo a `uint64` o verificar que `nonce <= type(uint64).max`:
  ```solidity
  uint256 invalidatorSlot = nonce >> 8;
  uint256 invalidatorBit = 1 << (nonce & 0xff);
  ```

---

### HALLAZGO ETH-02: Reinicio del Reloj de Cooldown en `StakedUSDeV2` (Severidad: MEDIA-ALTA)
- **Archivo:** `contracts/contracts/StakedUSDeV2.sol`
- **Líneas:** 96-105, 109-118
- **Descripción:**
  `StakedUSDeV2` gestiona el retiro de USDe a través del contrato `silo` con un periodo de enfriamiento de hasta 90 días (`cooldownDuration`).
  En `cooldownAssets`:
  ```solidity
  cooldowns[msg.sender].cooldownEnd = uint104(block.timestamp) + cooldownDuration;
  cooldowns[msg.sender].underlyingAmount += uint152(assets);
  ```
- **Impacto:**
  Si un usuario solicitó el retiro de 1,000,000 USDe y se encuentra a solo 1 hora de cumplir los 90 días de espera, y ejecuta un nuevo retiro menor (e.g. 1 wei o 10 USDe), el valor de `cooldownEnd` para la totalidad de sus fondos acumulados en `underlyingAmount` se sobreescribe con `block.timestamp + cooldownDuration`. Todo su capital previo queda atrapado por 90 días adicionales.
- **Remediación:**
  Permitir múltiples entradas de cooldown por usuario o calcular un vencimiento ponderado por saldo, evitando que un depósito menor posponga arbitrariamente la madurez de retiros preexistentes.

---

### HALLAZGO ETH-03: Posible Underflow Panic (`0x11`) en `StakedUSDe.totalAssets()` (Severidad: MEDIA)
- **Archivo:** `contracts/contracts/StakedUSDe.sol`
- **Línea:** 161-163
- **Descripción:**
  ```solidity
  function totalAssets() public view override returns (uint256) {
    return IERC20(asset()).balanceOf(address(this)) - getUnvestedAmount();
  }
  ```
  Si por cualquier evento contable o discrepancia temporal en la entrega de recompensas el balance de USDe en el contrato es menor que `getUnvestedAmount()`, la resta no verificada produce un desbordamiento inferior (`Panic 0x11`) en Solidity 0.8.20. Debido a que `previewDeposit`, `previewWithdraw`, `deposit`, `mint`, `withdraw` y `redeem` invocan `totalAssets()`, el contrato sUSDe queda completamente bloqueado.
- **Remediación:**
  ```solidity
  uint256 balance = IERC20(asset()).balanceOf(address(this));
  uint256 unvested = getUnvestedAmount();
  return balance > unvested ? balance - unvested : 0;
  ```

---

## 3. ASIGNACIÓN FORMAL DE HONORARIOS
- **Destinatario de Recompensa (Bug Bounty Payout):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Redes Soportadas:** Ethereum Mainnet, Arbitrum, Optimism, Base.
- **Moneda de Pago:** USDC (Reglas de Immunefi para Ethena).
