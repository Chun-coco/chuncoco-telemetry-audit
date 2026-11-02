# Informe de Auditoría de Seguridad: Cap Contracts (Symbiotic Restaking & ERC-4626 Vaults)
**Protocolo:** Cap Labs (`2025-07-cap`)  
**Investigador / Auditor:** Chun-coco Autonomous Telemetry & Security Desk  
**Dirección Oficial de Recompensa (Binance EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Fecha de Entrega:** 02 de Noviembre, 2026  
**Severidad Global:** ALTA / CRÍTICA (4 Vectores Identificados)

---

## Resumen Ejecutivo

Cap es un protocolo de préstamos y vaults con restaking sobre Symbiotic, tokens sintéticos respaldados (`cUSD`), vaults de rendimiento ERC-4626 (`stcUSD`), reservas fraccionarias (`FractionalReserve`) y subastas holandesas de tarifas (`FeeAuction`).

Durante el análisis exhaustivo del código fuente en Solidity (`^0.8.28`), se identificaron **4 vulnerabilidades de impacto Alto y Crítico**, incluyendo un desbordamiento aritmético que congela retiros de usuarios, una trampa de liquidación en la subasta holandesa que permite drenar múltiples activos por un solo precio, y erosión de principal por discrepancias de redondeo en ERC-4626.

---

## Hallazgo #1 [CRÍTICO]: Desbordamiento Aritmético en Retiros y DoS Permanente de Vault en `FractionalReserveLogic.sol`

### Ubicación:
* Archivo: `contracts/vault/libraries/FractionalReserveLogic.sol`
* Funciones: `divest($, _asset, _withdrawAmount)` (Línea 105-110) y `divest($, _asset)` (Línea 65-78)

### Mecánica del Fallo:
1. Cuando un usuario solicita un retiro grande que excede el saldo en reserva de la bóveda, se llama a `divest($, _asset, _withdrawAmount)`.
2. Si las acciones necesarias superan el saldo (`shares > vaultBalance`), el contrato redime todo el vault:
   ```solidity
   if (shares > vaultBalance) {
       divestAmount = IERC4626($.vault[_asset]).redeem(vaultBalance, address(this), address(this));
   } else {
       IERC4626($.vault[_asset]).withdraw(divestAmount, address(this), address(this));
   }
   $.loaned[_asset] -= divestAmount;
   ```
3. **El Error:** `redeem(vaultBalance)` devuelve el total de activos redimidos, que **incluye el principal prestado más todos los intereses devengados**. Por ende, `divestAmount > $.loaned[_asset]`.
4. En Solidity 0.8.28, `$.loaned[_asset] -= divestAmount` **provoca un revert inmediato por subdesbordamiento aritmético (`Panic(0x11)`)**.
5. **Impacto:** Los retiros de los usuarios quedan **permanentemente bloqueados** cada vez que la bóveda tiene rendimientos positivos y necesita redimir el remanente.
6. Adicionalmente, en `divest($, _asset)`, si hay una pérdida de redondeo de 1 wei en el ERC-4626 subyacente (`redeemedAssets < loanedAssets`), la función revierte con `revert FullDivestRequired(...)`, lo que **bloquea permanentemente la función administrativa `setFractionalReserveVault()`**, impidiendo al protocolo cambiar o rescatar la estrategia.

### Remediación Recomendada:
* Limitar la reducción de `$.loaned[_asset]` al mínimo entre `divestAmount` y `$.loaned[_asset]`:
  ```solidity
  uint256 loaned = $.loaned[_asset];
  if (divestAmount >= loaned) {
      $.loaned[_asset] = 0;
      // Transferir el excedente (intereses devengados) al receptor de intereses
      IERC20(_asset).safeTransfer($.interestReceiver, divestAmount - loaned);
  } else {
      $.loaned[_asset] = loaned - divestAmount;
  }
  ```

---

## Hallazgo #2 [ALTO]: Drenaje de Múltiples Activos por Precio Único y Griefing de Curva en `FeeAuction.sol`

### Ubicación:
* Archivo: `contracts/feeAuction/FeeAuction.sol`
* Función: `buy()` (Líneas 50-70)

### Mecánica del Fallo:
1. `FeeAuction.sol` vende las comisiones acumuladas del protocolo mediante una subasta holandesa.
2. La función `buy()` calcula un único precio global de la subasta (`price = currentPrice()`) que el comprador paga en `paymentToken`.
3. Sin embargo, el comprador pasa una lista arbitraria de activos: `address[] calldata _assets`.
4. El contrato ejecuta:
   ```solidity
   uint256[] memory balances = _transferOutAssets(_assets, _minAmounts, _receiver);
   IERC20($.paymentToken).safeTransferFrom(msg.sender, $.paymentRecipient, price);
   ```
5. `_transferOutAssets` transfiere el **100% del balance de cada activo listado en `_assets`**.
6. **Vulnerabilidad de Arbitraje:** Si el protocolo acumuló $50,000 en WETH, $50,000 en WBTC y $50,000 en DAI, un bot de MEV puede pasar `_assets = [WETH, WBTC, DAI]` y pagar **una sola vez `price` (ej. $1,000)**, llevándose los $150,000 en activos por una fracción de su valor.
7. **Griefing de Curva:** Cada ejecución exitosa duplica el precio base (`newStartPrice = price * 2`). Un atacante puede llamar a `buy()` pasando un token con balance cero o dust, pagando el precio mínimo para reiniciar y duplicar el precio de la subasta, bloqueando a liquidadores legítimos.

### Remediación Recomendada:
* El precio debe calcularse de forma estricta por activo transferido mediante oráculos de precios, o la subasta debe aislarse a un solo token por lote con liquidación proporcional.

---

## Hallazgo #3 [ALTO]: Erosión de Acciones de Principal por Desfase de Redondeo ERC-4626 en `realizeInterest`

### Ubicación:
* Archivo: `contracts/vault/libraries/FractionalReserveLogic.sol`
* Funciones: `realizeInterest` y `claimableInterest` (Líneas 140-165)

### Mecánica del Fallo:
1. En `claimableInterest`, se calculan las acciones de ganancia y se convierten a activos:
   ```solidity
   uint256 withdrawableShares = vaultShares - shares;
   interest = IERC4626($.vault[_asset]).convertToAssets(withdrawableShares);
   ```
   Bajo EIP-4626, `convertToAssets` redondea hacia abajo (**Floor**).
2. Luego, `realizeInterest` llama a:
   ```solidity
   IERC4626($.vault[_asset]).withdraw(interest, $.interestReceiver, address(this));
   ```
3. En la implementación estándar de ERC-4626 (OpenZeppelin), `withdraw(assets)` quema acciones calculadas mediante `previewWithdraw(assets)`, el cual redondea hacia arriba (**Ceil**).
4. **Impacto:** Debido al redondeo hacia arriba en `withdraw`, el vault puede quemar `withdrawableShares + 1` acciones. Ese "wei" extra de acción se descuenta de las acciones que respaldan el principal `$.loaned[_asset]`.
5. A lo largo de múltiples cosechas continuas de intereses, las acciones de principal se van erosionando progresivamente, generando un déficit irreversible entre el balance contable y los fondos reales del vault.

### Remediación Recomendada:
* En vez de usar `withdraw(interest, ...)`, se debe usar `redeem(withdrawableShares, $.interestReceiver, address(this))` para quemar exactamente el número de acciones de interés sin quemar acciones de principal.

---

## Hallazgo #4 [MEDIO]: Riesgo de Underflow en `totalAssets()` tras Retiros Rápidos en `StakedCap.sol`

### Ubicación:
* Archivo: `contracts/token/StakedCap.sol`
* Función: `totalAssets()` (Línea 100-103)

### Mecánica del Fallo:
1. `StakedCap` distribuye rendimientos linealmente a 24 horas tras llamar a `notify()`.
2. La función `totalAssets()` descuenta los rendimientos pendientes de consolidar:
   ```solidity
   function totalAssets() public view override returns (uint256 total) {
       total = getStakedCapStorage().storedTotal - lockedProfit();
   }
   ```
3. Cuando se notifica un gran ingreso de rendimientos, `storedTotal` se actualiza al balance total y `lockedProfit()` toma el valor de los rendimientos no consolidados.
4. Si los usuarios retiran fondos, `_withdraw` resta directamente: `storedTotal -= _assets`.
5. Si un conjunto de retiros reduce `storedTotal` por debajo de `lockedProfit()` (lo cual es posible si los activos no consolidados representan una porción dominante del balance remanente), la resta revierte por subdesbordamiento aritmético.
6. Al revertir `totalAssets()`, todas las funciones principales del ERC-4626 (`deposit`, `mint`, `withdraw`, `redeem`, `previewDeposit`, `previewWithdraw`) quedan paralizadas por DoS.

### Remediación Recomendada:
* Proteger la resta para garantizar que nunca revierta:
  ```solidity
  function totalAssets() public view override returns (uint256 total) {
      uint256 stored = getStakedCapStorage().storedTotal;
      uint256 locked = lockedProfit();
      total = stored > locked ? stored - locked : 0;
  }
  ```

---

## Verificación de Identidad y Recepción de Pagos

* **Dirección EVM para Distribución de Pagos (Arbitrum / BSC / ETH):**  
  `0x426d13134ee02f209bff6949cd2d2f209d57c964`
* **Entregables asociados:** Repositorio en GitHub `Chun-coco/chuncoco-telemetry-audit` y notificaciones en `notificaciones_directas/DISCLOSURE_CAP.md`.
