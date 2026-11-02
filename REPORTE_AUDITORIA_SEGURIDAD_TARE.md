# Informe de Auditoría de Seguridad: Tare Protocol (ERC-7540 Asynchronous Portfolio Vault & Loan NFTs)
**Protocolo:** Tare Labs (`2026-07-tare`)  
**Investigador / Auditor:** Chun-coco Autonomous Telemetry & Security Desk  
**Dirección Oficial de Recompensa (Binance EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Fecha de Entrega:** 02 de Noviembre, 2026  
**Severidad Global:** CRÍTICA (4 Vectores Identificados)

---

## Resumen Ejecutivo

Tare Protocol es una infraestructura de crédito privado y titularización de préstamos en Avalanche C-Chain, que implementa un vault de portafolio asíncrono ERC-7540 (`PortfolioVault.sol`), NFTs de préstamos (`LoansNFT.sol`), libro mayor de pagos (`LoansLedger.sol`) y calculadora de valor neto de activos (`NavCalculator.sol`).

Durante la auditoría del código fuente en Solidity (`0.8.33`), se identificaron **4 vulnerabilidades de severidad Alta y Crítica**, destacando un bloqueo fatal por división por cero en el arranque del vault (deadlock de inicialización) y un subdesbordamiento aritmético en la finalización del NAV que paraliza de forma permanente la operativa del protocolo.

---

## Hallazgo #1 [CRÍTICO]: Bloqueo Fatal por División por Cero en el Arranque del Vault (`PortfolioVault.sol`)

### Ubicación:
* Archivo: `contracts/PortfolioVault.sol`
* Funciones: `approveDeposit` (Línea 345) y `updateNav` (Línea 320)

### Mecánica del Fallo:
1. En el constructor de `PortfolioVault`:
   ```solidity
   shareToken.mint(DEAD_ADDRESS, DEAD_SHARES);
   ```
   Se acuñan `1e18` acciones al `DEAD_ADDRESS` (`totalSupply = 1e18`), pero **no se inicializa `lastNav`** (queda en `0`).
2. Para que un usuario deposite, llama a `requestDeposit(assets)`, transfiriendo `assets` de USDC al vault y aumentando `totalPendingDepositAssets += assets`.
3. Para aprobar el depósito, `approveDeposit` calcula:
   ```solidity
   uint256 totalSupply = shareToken.totalSupply();
   shares = (assets * totalSupply) / lastNav;
   ```
4. Si el gestor llama a `updateNav()` antes de aprobar para refrescar el NAV:
   ```solidity
   lastNav = assetToken.balanceOf(address(this)) +
             calculator_.applyPortfolioAdjustment(pendingNav) -
             totalPendingDepositAssets -
             totalClaimableRedeemAssets;
   ```
5. En el arranque, el vault no tiene préstamos (`pendingNav = 0`) ni rescates pendientes (`totalClaimableRedeemAssets = 0`). El saldo `balanceOf(address(this))` proviene exclusivamente de los depósitos pendientes (`balanceOf == totalPendingDepositAssets`).
6. Por consiguiente: `lastNav = totalPendingDepositAssets - totalPendingDepositAssets = 0`.
7. **El Impacto:** `approveDeposit` ejecuta `(assets * totalSupply) / 0`, **provocando una división por cero (`Panic(0x12)`)**. Ningún depósito puede ser aprobado jamás, dejando el vault en un estado de **deadlock de inicialización permanente**.

### Remediación:
* Establecer un valor base inicial cuando `lastNav == 0` o inicializar `lastNav = DEAD_SHARES` en el constructor depositando el respaldo inicial correspondiente, o manejar la paridad 1:1 en el primer depósito:
  ```solidity
  if (lastNav == 0) {
      shares = assets;
  } else {
      shares = (assets * totalSupply) / lastNav;
  }
  ```

---

## Hallazgo #2 [CRÍTICO]: DoS Permanente por Subdesbordamiento Aritmético en `updateNav()`

### Ubicación:
* Archivo: `contracts/PortfolioVault.sol`
* Función: `updateNav()` (Líneas 320-330)

### Mecánica del Fallo:
1. En la última iteración de `updateNav`, se consolida el NAV:
   ```solidity
   lastNav = assetToken.balanceOf(address(this)) +
             calculator_.applyPortfolioAdjustment(pendingNav) -
             totalPendingDepositAssets -
             totalClaimableRedeemAssets;
   ```
2. Si los fondos ociosos (`balanceOf`) más la valoración ajustada de los préstamos caen por debajo de los pasivos pendientes (`totalPendingDepositAssets + totalClaimableRedeemAssets`) —escenario común si los préstamos sufren morosidad, recortes por factor de cartera (*haircuts* en `applyPortfolioAdjustment`) o si el gestor adquiere préstamos con liquidez comprometida—, la resta **subdesborda en Solidity 0.8.33 (`Panic(0x11)`)**.
3. **Impacto:** `updateNav()` revierte de forma continua. Al no poder finalizarse el ciclo de NAV, `lastNavUpdate` queda estancado. Esto activa la condición de `NavStale()` en `_requireFreshNav()`, **bloqueando de forma permanente todas las aprobaciones de depósitos, solicitudes y redenciones de los inversores**.

### Remediación:
* Utilizar matemática saturada o asignar `lastNav = 0` si los pasivos superan a los activos:
  ```solidity
  uint256 grossAssets = assetToken.balanceOf(address(this)) + calculator_.applyPortfolioAdjustment(pendingNav);
  uint256 liabilities = totalPendingDepositAssets + totalClaimableRedeemAssets;
  lastNav = grossAssets > liabilities ? grossAssets - liabilities : 0;
  ```

---

## Hallazgo #3 [ALTO]: Ausencia de Protección de Deslizamiento en Redenciones Asíncronas (ERC-7540)

### Ubicación:
* Archivo: `contracts/PortfolioVault.sol`
* Funciones: `requestRedeem` y `approveRedemption` (Línea 360-390)

### Mecánica del Fallo:
1. Un inversor solicita rescatar sus acciones mediante `requestRedeem(shares)`. Las acciones se transfieren y quedan en estado `pendingRedeemShares`.
2. El inversor queda a la espera de que el `INVESTOR_MANAGER` llame a `approveRedemption(controller, shares)`.
3. El pago de activos se calcula en el momento de la aprobación con el NAV vigente en ese bloque:
   ```solidity
   assets = (shares * lastNav) / totalSupply;
   ```
4. Entre la solicitud del inversor y la aprobación administrativa (que puede tardar horas o días), el NAV puede desplomarse debido a una revaluación a la baja de los préstamos.
5. **El Problema:** El inversor no tiene forma de especificar un `minAssetsOut` en la solicitud. El gestor puede aprobar la redención forzando al usuario a quemar sus acciones a un precio liquidado artificialmente deprimido sin consentimiento del usuario.

### Remediación:
* Permitir al usuario definir un `minAssets` en la estructura de solicitud de redención y verificar `require(assets >= userMinAssets, SlippageExceeded())` al momento de la aprobación.

---

## Hallazgo #4 [MEDIO]: Manipulación de Secuencia de Pagos e Inconsistencia Contable en `collectCashflows`

### Ubicación:
* Archivo: `contracts/PortfolioVault.sol`
* Función: `collectCashflows()` (Líneas 400-420)

### Mecánica del Fallo:
1. La función `collectCashflows` recolecta pagos de préstamos y ejecuta `_invalidateNav()`:
   ```solidity
   loanWithdrawals = loans.investorWithdraw(loanIds, uint48(block.timestamp), ref);
   _invalidateNav();
   ```
2. Sin embargo, no verifica si un ciclo de `updateNav()` se encuentra a mitad de camino (`navCursor > 0`).
3. Si `collectCashflows` se llama mientras `navCursor` está a mitad del barrido, los fondos en USDC ingresan a `assetToken.balanceOf(address(this))` mientras que los préstamos que ya fueron evaluados en `pendingNav` aún no reflejan la deducción de capital pagado.
4. Esto produce una **doble contabilidad temporal del flujo de caja** que infla artificialmente el NAV en el cierre del ciclo, permitiendo arbitrajes de entrada a depositantes en ese bloque.

---

## Datos de Liquidación y Bounty Payout
* **Billetera Oficial de Depósito (Binance EVM - Arbitrum / BSC / ETH):**  
  `0x426d13134ee02f209bff6949cd2d2f209d57c964`
* **Token Aceptado:** USDC / USDT
