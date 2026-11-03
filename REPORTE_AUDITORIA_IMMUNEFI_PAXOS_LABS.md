# INFORME DE AUDITORÍA DE SEGURIDAD IMMUNEFI: PAXOS LABS (PXL-BORING-VAULT & PAXGY)

**Protocolo:** Paxos Labs (`paxoslabs/pxl-boring-vault`)  
**Programa Activo:** [Immunefi Bug Bounty Program - Paxos Labs](https://immunefi.com/bug-bounty/paxos-labs/)  
**Estado del Programa:** ACTIVO (Actualizado 23 de Octubre de 2026, sin fecha de término `endDate: null`)  
**Bolsa Total de Recompensas:** Hasta $500,000 USDG  
**Severidad Global de Hallazgos:** ALTA (High) / MEDIA (Medium)  
**Activos en Alcance Auditados:**
- `src/base/Roles/WithdrawQueue.sol` (`0x69e0BF658bE5600864A946b4e5B911736D248FB4`)
- `src/helper/one-to-one-queue/OneToOneQueue.sol`
- `src/helper/PaxgyDynamicWithdrawalFeeModule.sol` (`0xF41e79D6e646f334C2fc4ea5Ae609707AE82264D`)
- `src/oracles/PaxgXauRateProvider.sol`
- `src/base/Roles/AccountantWithRateProviders.sol` (`0x397e38359f169748a02bc11f98D4f451FE88C1fd`)
- `src/base/Roles/TellerWithMultiAssetSupport.sol` (`0x41AB5d8387e60E30AACCF11357C306f6d875A6f7`)
**Dirección Oficial de Cobro EVM:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Investigador:** Chun-coco Security Research Group (`@chuncoco`)  

---

## 1. RESUMEN EJECUTIVO

Paxos Labs opera la infraestructura de bóvedas de rendimiento institucional `pxl-boring-vault` en Ethereum Mainnet para tokens respaldados por oro físico y activos regulados (PAXG, PAXGy). Los contratos en alcance gestionan el ciclo completo de depósitos ponderados por NAV, cálculo de comisiones dinámicas por desanclaje de mercado (`PaxgyDynamicWithdrawalFeeModule`), oráculos de tasa cruzada oro/dólar (`PaxgXauRateProvider`) y colas de retiro secuencial (`WithdrawQueue` y `OneToOneQueue`).

La auditoría formal de código de producción reveló **fallos severos de denegación de servicio por bloqueo de cabecera de cola (*Head-of-Line Blocking*), congelamiento de retiros y cancelaciones por dependencias de oráculo fuera de horario bursátil, y discrepancias de autorización en funciones de usuario**.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

```
+---------------+--------------------------------------------------------------------------------+--------------+
| ID            | Título de la Vulnerabilidad                                                    | Severidad    |
+---------------+--------------------------------------------------------------------------------+--------------+
| PAXOS-HIGH-01 | DoS de Cola de Retiros por Bloqueo de Cabecera (Head-of-Line Blocking)         | ALTA         |
| PAXOS-HIGH-02 | Congelamiento de Procesamiento de Retiros y Reembolsos por Oráculo XAU Inactivo| ALTA         |
| PAXOS-HIGH-03 | Modificador `requiresAuth` Impide Cancelaciones de Órdenes a Usuarios Legítimos| ALTA         |
| PAXOS-MED-01  | Acciones en Vault Inflan Tarifas de Gestión en `AccountantWithRateProviders`   | MEDIA        |
| PAXOS-MED-02  | Pánico Incontrolado por `assert` en `WithdrawQueue.processOrders`              | MEDIA        |
+---------------+--------------------------------------------------------------------------------+--------------+
```

---

### PAXOS-HIGH-01: DoS de Cola de Retiros por Bloqueo de Cabecera (Head-of-Line Blocking)

- **Impacto Immunefi:** *Temporary/Permanent freezing of funds*
- **Severidad:** ALTA (High)
- **Archivos Afectados:**
  - `src/base/Roles/WithdrawQueue.sol` (Líneas 530-534)
  - `src/helper/one-to-one-queue/OneToOneQueue.sol` (Líneas 515, 636-640)

#### Mecánica del Fallo:
En `WithdrawQueue.processOrders`:
```solidity
uint256 vaultBalanceOfWantAsset = order.wantAsset.balanceOf(address(vault));
if (vaultBalanceOfWantAsset < expectedAssetsOut) {
    revert VaultInsufficientBalance(order.wantAsset, expectedAssetsOut, vaultBalanceOfWantAsset);
}
```
Y análogamente en `OneToOneQueue.sol`:
```solidity
function _checkBalanceQueue(IERC20 asset, uint256 amount, uint256 orderIndex) internal view {
    uint256 balance = asset.balanceOf(address(this));
    if (balance < amount) {
        revert InsufficientBalanceInQueue(orderIndex, address(asset), amount, balance);
    }
}
```
Las órdenes de retiro se organizan en una cola FIFO estricta que se procesa secuencialmente mediante `processOrders(ordersToProcess)` partiendo de `lastProcessedOrder + 1`.

Si una orden cualquiera en la cola (por ejemplo, una orden grande de un usuario institucional o ballena por 1,000 PAXG) supera la liquidez disponible de la bóveda en ese instante:
1. La función ejecuta un `revert` atómico con `VaultInsufficientBalance` / `InsufficientBalanceInQueue`.
2. Toda la ejecución de `processOrders` revierte.
3. **El cursor de la cola (`lastProcessedOrder`) no puede avanzar.**
4. Todas las órdenes posteriores (órdenes pequeñas de 1 a 10 PAXG que sí podrían satisfacerse perfectamente con la liquidez actual de la bóveda) quedan **100% bloqueadas e imposibilitadas de cobrar**.
5. Los usuarios afectados no pueden forzar el procesamiento de sus órdenes porque `forceProcessOrders` requiere privilegios de administración (`requiresAuth`).

#### Remediación Defensiva:
Si una orden carece de liquidez suficiente en la bóveda, no revertir la transacción completa; en su lugar, saltar la orden o marcarla temporalmente como diferida para permitir que las órdenes menores con liquidez suficiente continúen liquidándose.

---

### PAXOS-HIGH-02: Congelamiento de Procesamiento de Retiros y Reembolsos por Oráculo XAU Inactivo

- **Impacto Immunefi:** *Temporary freezing of funds*
- **Severidad:** ALTA (High)
- **Archivos Afectados:**
  - `src/oracles/PaxgXauRateProvider.sol` (Líneas 115-135)
  - `src/helper/PaxgyDynamicWithdrawalFeeModule.sol` (Línea 105)
  - `src/base/Roles/WithdrawQueue.sol` (Línea 510)

#### Mecánica del Fallo:
`PaxgXauRateProvider` consulta el feed de Chainlink `XAU / USD` (oro spot contra dólar) y aplica:
```solidity
(, int256 _xauUsd,, uint256 lastUpdatedAtXau,) = XAU_USD_FEED.latestRoundData();
if (block.timestamp - lastUpdatedAtXau > MAX_TIME_FROM_LAST_UPDATE) {
    revert MaxTimeFromLastUpdatePassed(block.timestamp, lastUpdatedAtXau);
}
```
El oro físico (XAU) cotiza en mercados financieros tradicionales que **cierran durante los fines de semana y días festivos**, periodo durante el cual el feed de Chainlink no emite actualizaciones periódicas. Si el lapso supera `MAX_TIME_FROM_LAST_UPDATE`, la llamada revierte.

En `WithdrawQueue.processOrders`:
```solidity
uint256 feeAmount = feeModule.calculateOfferFees(order.amountOffer, offerAsset, order.wantAsset, receiver);
```
Esta llamada se realiza de forma directa **sin protección `try/catch`**.
Cuando el feed de oro queda inactivo por cierre de mercado o retraso de red, `calculateOfferFees` revierte, **paralizando el 100% del procesamiento de retiros de la cola**.
Adicionalmente, los usuarios que solicitaron la cancelación de su orden no reciben su reembolso de inmediato; la orden se marca como `REFUND` y requiere que `processOrders` avance hasta su índice. Al revertir en las órdenes previas, **los reembolsos también quedan completamente congelados**.

#### Remediación Defensiva:
1. Envolver la llamada `calculateOfferFees` en un bloque `try/catch` con tasa de respaldo segura de paridad 1:1 o diferir el cálculo dinámico.
2. Permitir el retiro inmediato de fondos para órdenes marcadas como `REFUND` sin depender de que `processOrders` avance secuencialmente.

---

### PAXOS-HIGH-03: Modificador `requiresAuth` Impide Cancelaciones de Órdenes a Usuarios Legítimos

- **Impacto Immunefi:** *Unauthorized denial of service on user rights*
- **Severidad:** ALTA (High)
- **Archivo Afectado:** `src/base/Roles/WithdrawQueue.sol` (Líneas 309-335)

#### Mecánica del Fallo:
La documentación del contrato (`natspec`) indica expresamente:
```solidity
/**
 * @notice A user facing function for users to cancel their own orders
 * @dev This is a public function made for users to cancel their own orders that they must be the owner of
 * @param orderIndex Index of the order to cancel
 */
function cancelOrder(uint256 orderIndex) external requiresAuth {
    if (ownerOf(orderIndex) != msg.sender) revert OnlyOrderOwnerCanCancel(msg.sender, ownerOf(orderIndex));
    _markOrderForRefund(orderIndex, true);
}
```
Y para firmas fuera de cadena:
```solidity
function cancelOrderWithSignature(...) external requiresAuth
```
Ambas funciones incorporan el modificador `requiresAuth`.
Bajo el sistema `Auth` de Solmate, `requiresAuth` restringe la llamada exclusivamente al propietario del contrato o a cuentas autorizadas en la `Authority`.
Un usuario estándar que depositó y recibió el token de recibo ERC-721 **no es administrador ni está en la lista de autorización**. Salvo que el administrador configure una regla abierta global para ese selector en `RolesAuthority`, cualquier intento de cancelación por parte del usuario legítimo falla con el error `"UNAUTHORIZED"`, atrapando al usuario en la cola contra su voluntad.

#### Remediación Defensiva:
Eliminar el modificador `requiresAuth` de `cancelOrder` y `cancelOrderWithSignature`, ya que la seguridad de la función está garantizada por la verificación intrínseca `ownerOf(orderIndex) == msg.sender` y la firma criptográfica EIP-712.

---

### PAXOS-MED-01: Acciones en Vault Inflan Tarifas de Gestión en `AccountantWithRateProviders`

- **Impacto Immunefi:** *Financial miscalculation / Overcharging fees*
- **Severidad:** MEDIA (Medium)
- **Archivo Afectado:** `src/base/Roles/AccountantWithRateProviders.sol` (Línea 346)

#### Mecánica del Fallo:
Cuando `WithdrawQueue` deduce comisiones por desanclaje en acciones, las transfiere a `feeRecipient = address(vault)`.
El Natspec de `PaxgyDynamicWithdrawalFeeModule` advierte explícitamente:
> *"NOTE: shares sent to the vault are NOT burned by the ERC20; for these fees to actually accrue to NAV, the fee recipient and the offchain NAV calculation must treat vault-held shares as nonexistent (excluded from both total value and total supply)."*

Sin embargo, en `AccountantWithRateProviders.updateExchangeRate`:
```solidity
uint256 currentTotalShares = vault.totalSupply();
```
El contrato lee `vault.totalSupply()` de manera bruta sin restar `vault.balanceOf(address(vault))`.
Al calcular la comisión de gestión sobre un suministro total que incluye las acciones acumuladas en la propia bóveda, se cobran comisiones sobre participaciones inexistentes/no circulantes, diluyendo a los tenedores reales.

#### Remediación Defensiva:
Deducir el balance de la bóveda del suministro total:
```solidity
uint256 currentTotalShares = vault.totalSupply() - vault.balanceOf(address(vault));
```

---

### PAXOS-MED-02: Pánico Incontrolado por `assert` en `WithdrawQueue.processOrders`

- **Impacto Immunefi:** *Griefing / Reversion of valid batches*
- **Severidad:** MEDIA (Medium)
- **Archivo Afectado:** `src/base/Roles/WithdrawQueue.sol` (Línea 545)

#### Mecánica del Fallo:
```solidity
try tellerWithMultiAssetSupport.bulkWithdraw(...) returns (uint256 assetsOut) {
    if (assetsOut == 0) {
        revert InvalidAssetsOut();
    }
    assert(assetsOut == expectedAssetsOut);
    ...
} catch {
```
En Solidity 0.8+, la sentencia `assert(assetsOut == expectedAssetsOut)` lanza `Panic(0x01)`. Al encontrarse dentro del bloque de retorno exitoso de la llamada externa, esta excepción no es atrapada por el bloque `catch`. Cualquier discrepancia de 1 wei por redondeo o cálculo de tasa trunca la ejecución completa del lote de órdenes.

#### Remediación Defensiva:
Sustituir `assert` por un `require` descriptivo o manejar tolerancias de redondeo mínimas (1 wei).

---

## 3. DATOS DE ADJUDICACIÓN DE RECOMPENSA

- **Programa Objetivo:** Paxos Labs (`paxos-labs`) en Immunefi
- **Wallet de Pago (EVM):**
  `0x426d13134ee02f209bff6949cd2d2f209d57c964`
