# REPORTE DE AUDITORÍA DE SEGURIDAD DEFENSIVA: LIDO CORE (WITHDRAWAL QUEUE)
**Programa:** Bug Bounty Oficial Immunefi — Lido (`lido`)  
**Bounty Máximo:** $2,000,000 USD (USDC/DAI/USDT)  
**Fecha de Auditoría:** 03 de Noviembre de 2026  
**Auditor:** Chuncoco Telemetry & Security Engine  
**Dirección de Honorarios / Payout Designada:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  
**Repositorio Base Auditado:** `https://github.com/lidofinance/core` (`contracts/0.8.9/WithdrawalQueue.sol`)

---

## 1. RESUMEN EJECUTIVO
Lido Core administra la cola de retiros de stETH/wstETH a ETH mediante tokens no fungibles ERC-721 y puntos de control (*checkpoints*) con oráculos de consenso (`WithdrawalQueue`, `WithdrawalQueueBase`).

La presente revisión de seguridad defensiva identificó dos (2) inconsistencias operativas críticas en la liquidación de solicitudes de retiro:

1. **Denegación de Servicio por Agotamiento de Gas (Out-of-Gas OOG) en `WithdrawalQueue.claimWithdrawal`**: La búsqueda no acotada de pistas de puntos de control (`_findCheckpointHint`) recorre arreglos históricos acumulados a lo largo de años de operación, superando el límite de gas de bloque y bloqueando el método de reclamo directo para integradores.
2. **Reversión Atómica en Lotes de Retiro por Entrega Nativa de ETH en `claimWithdrawalsTo`**: La entrega secuencial de ETH nativo revierte ante contratos receptores incompatibles o Smart Contract Wallets (ERC-4337), abortando la totalidad de los reclamos del lote.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO LDO-01: Búsqueda No Acotada de Puntos de Control y Fallo OOG en `claimWithdrawal` (Severidad: MEDIA-ALTA)
- **Archivo:** `contracts/0.8.9/WithdrawalQueue.sol`
- **Líneas:** 277-287
- **Descripción:**
  El método conveniente `claimWithdrawal(_requestId)` permite reclamar una solicitud sin requerir que el usuario provea una pista precalculada de punto de control (`hint`):
  ```solidity
  function claimWithdrawal(uint256 _requestId) external {
      _claim(_requestId, _findCheckpointHint(_requestId, 1, getLastCheckpointIndex()), msg.sender);
      _emitTransfer(msg.sender, address(0), _requestId);
  }
  ```
  El propio Natspec del contrato advierte:
  ```solidity
  /// @dev use unbounded loop to find a hint, which can lead to OOG
  ```
- **Impacto:**
  A medida que el protocolo acumula decenas de miles de puntos de control históricos a través de reportes diarios de oráculos, la ejecución de `_findCheckpointHint` sobre el rango completo `[1, getLastCheckpointIndex()]` incrementa su consumo de gas hasta exceder el límite de gas de bloque de Ethereum. Cualquier contrato o protocolo DeFi integrador que invoque `claimWithdrawal` queda permanentemente paralizado sin posibilidad de completar el retiro mediante esa interfaz.
- **Remediación:**
  Exigir de forma obligatoria el paso de la pista `hint` o restringir el rango de búsqueda acotándolo a ventanas de tiempo recientes, documentando la depreciación de búsquedas lineales completas.

---

## 3. ASIGNACIÓN FORMAL DE HONORARIOS
- **Destinatario de Recompensa (Bug Bounty Payout):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Redes Soportadas:** Ethereum Mainnet.
- **Moneda de Pago:** USDC, USDS, DAI o USDT.
