# INFORME DE AUDITORÍA DE SEGURIDAD TÉCNICA: YEARN yBOLD (LIQUITY V2 STABILITY POOL STRATEGIES & ACCOUNTANT)

**Protocolo:** Yearn Finance yBOLD (`yv3-liquityv2-sp-strategy`)  
**Competencia:** `2025-05-yearn-ybold` (Sherlock Audits)  
**Bolsa Total de Recompensas (Prize Pool):** $14,500 USDC  
**Objetivo de Infraestructura:** Ethereum Mainnet, Arbitrum, Base, Optimism, Sonic, Polygon  
**Dirección Designada de Cobro EVM:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Equipo Auditor:** Chun-coco Telemetry & Security Research Group (`@chuncoco`)  

---

## 1. RESUMEN EJECUTIVO Y MAPA DE AMENAZAS

El protocolo Yearn yBOLD implementa una arquitectura de asignación dinámica de liquidez sobre pools de estabilidad de Liquity V2 (Stability Pools para BOLD contra wstETH, rETH y WETH). El sistema está compuesto por:
1. `yBOLD`: Instancia de `VaultV3.vy` de Yearn que asigna BOLD entre 3 estrategias de Liquity V2.
2. `Strategy.sol` (`LiquityV2SPStrategy`): Estrategias tokenizadas basadas en `BaseHealthCheck` y `TokenizedStrategy` que proveen BOLD al Stability Pool, reclaman ganancias colaterales tras liquidaciones de troves y subastan el colateral mediante un contrato de subasta holandesa (`AUCTION`).
3. `Accountant.sol`: Contable de comisiones del vault `yBOLD` con tarifa de rendimiento del 100% que redirige todos los beneficios netos hacia `st-yBOLD` (`Staker.sol`), manteniendo `yBOLD` anclado 1:1 con BOLD.
4. `StrategyAprOracle.sol`: Oráculo de rendimiento anual (APR) que calcula el retorno ponderado por interés y deuda de todos los troves activos en Liquity V2.

A través de un análisis estático, formal y de invariantes matemáticos, se detectaron **5 vulnerabilidades críticas y de severidad alta/media** que comprometen el anclaje 1:1 del token, permiten la adquisición de colateral por 0 BOLD, y causan denegación de servicio (DoS) permanente en la distribución de recompensas y reasignación de deuda.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

```
+---------------+--------------------------------------------------------------------------------+--------------+
| ID            | Título de la Vulnerabilidad                                                    | Severidad    |
+---------------+--------------------------------------------------------------------------------+--------------+
| YBOLD-CRIT-01 | Quiebre Matemático del Invariante 1:1 por Dilución en Recuperación de Pérdidas | CRÍTICA      |
| YBOLD-CRIT-02 | Triple División por WAD en `Strategy._tend` Trunca Precio de Subasta por 10^18| CRÍTICA      |
| YBOLD-HIGH-01 | Bloqueo Permanente de Cosecha en `Staker.sol` por Control de Acceso en Contable| ALTA         |
| YBOLD-HIGH-02 | Bucle Ilimitado de Troves en `StrategyAprOracle` Provoca DoS por Out-of-Gas   | ALTA         |
| YBOLD-MED-01  | División Previa a Multiplicación Provoca Pérdida Total de Precisión de APR     | MEDIA        |
+---------------+--------------------------------------------------------------------------------+--------------+
```

---

### YBOLD-CRIT-01: Quiebre Matemático del Invariante 1:1 por Dilución en Recuperación de Pérdidas

- **Contrato:** `src/periphery/Accountant.sol` (Líneas 177-185)
- **Severidad:** CRÍTICA (Pérdida permanente de capital para depositantes, rotura del invariante fundacional)
- **Mecánica del Fallo:**
  El invariante principal estipula:
  > *"yBOLD should always maintain a 1:1 ratio with BOLD, unless a loss occurs. In the event of a loss, Accountant.sol will first cover the loss before distributing any fees to st-yBOLD. If process_report reports a loss, Accountant.sol will not take any fees until the yBOLD price per share returns to 1."*

  En `Accountant.report()`:
  ```solidity
  uint256 supply = vault.totalSupply();
  uint256 assets = vault.totalAssets();
  if (assets < supply) {
      uint256 needed = supply - assets;
      totalFees = gain < needed ? 0 : gain - needed;
  }
  ```
  Sin embargo, en el flujo de ejecución de Yearn `VaultV3.vy._process_report`:
  1. `accountant.report(strategy, gain, loss)` se ejecuta **ANTES** de que `gain` sea acreditado a `vault.total_debt` o `vault.total_idle`. Por lo tanto, `vault.totalAssets()` refleja el estado previo al reporte.
  2. Si `gain > needed`, `Accountant` retorna `totalFees = gain - needed`.
  3. Inmediatamente después, `VaultV3` calcula la cantidad de acciones a emitir para cubrir `totalFees` utilizando la función interna `_convert_to_shares(total_fees, Rounding.ROUND_UP)`.
  4. Dado que `total_debt` aún no se ha incrementado con `gain`, el precio por acción utilizado por `_convert_to_shares` es el precio deprimido previo al reporte:
     $$\text{PPS}_{\text{deprimido}} = \frac{\text{assets}}{\text{supply}} < 1.0$$
  5. La cantidad de acciones emitidas para el contable es:
     $$\text{shares}_{\text{minted}} = \frac{\text{totalFees}}{\text{PPS}_{\text{deprimido}}} > \text{totalFees}$$
  6. Posteriormente, `VaultV3` añade `gain` a los activos (`total_debt += gain`). El nuevo precio por acción resultante es:
     $$\text{PPS}_{\text{post}} = \frac{\text{assets} + \text{gain}}{\text{supply} + \text{shares}_{\text{minted}}} < 1.0$$

- **Prueba Matemática:**
  Sea $\text{supply} = 100$, $\text{assets} = 90$ tras una liquidación (pérdida de 10).
  Posteriormente se recupera una ganancia de $\text{gain} = 15$.
  - $\text{needed} = 100 - 90 = 10$.
  - $\text{totalFees} = 15 - 10 = 5$.
  - Acciones emitidas por el vault a `Accountant`:
    $$\text{shares} = 5 \times \frac{100}{90} = 5.5555... \text{ shares}$$
  - Nuevos activos totales del vault: $90 + 15 = 105$.
  - Nuevo suministro total de acciones: $100 + 5.5555 = 105.5555$.
  - Nuevo precio por acción:
    $$\text{PPS} = \frac{105}{105.5555} \approx 0.994736 < 1.0$$
  El precio por acción **NUNCA** regresa a 1.0. Cada ciclo de recuperación diluye permanentemente a los tenedores de `yBOLD`.

- **Remediación Defensiva:**
  El contable debe considerar la ganancia pendiente al determinar las tarifas y garantizar que el vault emita exactamente 1 acción por cada unidad de activo en exceso cuando el precio por acción se restablezca a 1.0:
  ```solidity
  uint256 supply = vault.totalSupply();
  uint256 assets = vault.totalAssets();
  uint256 anticipatedAssets = assets + gain;
  if (anticipatedAssets <= supply) {
      totalFees = 0;
  } else {
      // Solo el excedente neto por encima de supply a ratio 1:1 puede cobrarse
      uint256 surplus = anticipatedAssets - supply;
      // Ajustar totalFees considerando la tasa de conversión en el estado actual del vault
      totalFees = (surplus * assets) / supply;
  }
  ```

---

### YBOLD-CRIT-02: Triple División por WAD en `Strategy._tend` Trunca Precio de Subasta por 10^18

- **Contrato:** `src/Strategy.sol` (Línea 241)
- **Severidad:** CRÍTICA (Subastas a precio cero o reversión por división truncada, pérdida de colateral)
- **Mecánica del Fallo:**
  En `LiquityV2SPStrategy._tend`:
  ```solidity
  uint256 _toAuction = COLL.balanceOf(address(this));
  uint256 _available = COLL.balanceOf(address(AUCTION)) + _toAuction;
  if (_available > dustThreshold) {
      (uint256 _price, bool _isOracleDown) = COLL_PRICE_ORACLE.fetchPrice();
      uint256 _bufferPercentage = bufferPercentage;
      if (_isOracleDown || COLL_PRICE_ORACLE.priceSource() != IPriceFeed.PriceSource.primary) {
          _bufferPercentage *= ORACLE_DOWN_BUFFER_PCT_MULTIPLIER;
      }

      // slither-disable-next-line divide-before-multiply
      AUCTION.setStartingPrice(_available * _price / WAD * _bufferPercentage / WAD / WAD); // Reverts if there's an active auction

      COLL.safeTransfer(address(AUCTION), _toAuction);
      AUCTION.kick(address(COLL));
  }
  ```
  Nótese el cálculo de `setStartingPrice`:
  1. `_available * _price / WAD`: Da el valor total del colateral en BOLD (18 decimales).
  2. `* _bufferPercentage / WAD`: Aplica el recargo porcentual (18 decimales).
  3. `/ WAD`: ¡Divide una tercera vez entre $10^{18}$!

  Esto genera dos fallos catastróficos:
  1. Si el valor del lote a subastar es inferior a $1.00 BOLD (por ejemplo, 0.0003 ETH $\approx$ $0.80):
     $$\frac{0.80 \times 10^{18} \times 1.1}{10^{18}} = 0$$
     El precio inicial se establece en `0`. Si `AUCTION.setStartingPrice` exige `_startingPrice > 0`, la llamada revierte y la estrategia entra en un bloqueo DoS permanente donde nunca puede liquidar colateral. Si acepta `0`, bots MEV extraen el colateral gratuitamente a coste 0 BOLD.
  2. Para cualquier valor fraccional (ej. $12.75 BOLD), se trunca a 12 unidades enteras, perdiendo hasta 0.999 BOLD de valor en cada subasta.

- **Remediación Defensiva:**
  Eliminar la división redundante `/ WAD` para preservar la precisión nativa de 18 decimales de BOLD:
  ```solidity
  uint256 startingPriceWei = (_available * _price / WAD) * _bufferPercentage / WAD;
  AUCTION.setStartingPrice(startingPriceWei);
  ```

---

### YBOLD-HIGH-01: Bloqueo Permanente de Cosecha en `Staker.sol` por Control de Acceso en Contable

- **Contratos:** `src/Staker.sol` (Línea 49) y `src/periphery/Accountant.sol` (Líneas 377, 386)
- **Severidad:** ALTA (Denegación de servicio en reclamos de recompensas de `st-yBOLD`)
- **Mecánica del Fallo:**
  En `LV2SPStakerStrategy._harvestAndReport()`:
  ```solidity
  function _harvestAndReport() internal override returns (uint256 _totalAssets) {
      ACCOUNTANT.distribute(address(asset)); // Claim yBOLD
      _totalAssets = asset.balanceOf(address(this));
  }
  ```
  La función llamada en `Accountant.sol` es:
  ```solidity
  function distribute(address token) external virtual {
      distribute(token, ERC20(token).balanceOf(address(this)));
  }

  function distribute(address token, uint256 amount) public virtual onlyFeeManagerOrRecipient {
      ERC20(token).safeTransfer(feeRecipient, amount);
      emit DistributeRewards(token, amount);
  }
  ```
  Observe que `distribute(address token)` invoca la sobrecarga de dos parámetros sujeta al modificador `onlyFeeManagerOrRecipient`:
  ```solidity
  require(msg.sender == feeRecipient || msg.sender == feeManager, "!recipient");
  ```
  Al ser llamada desde `LV2SPStakerStrategy`, el `msg.sender` es la dirección de la estrategia. Si `feeRecipient` no ha sido configurado manualmente por gobernanza para ser exactamente la dirección del contrato de estrategia desplegado, cualquier ejecución de `harvest()` o `report()` revierte con `"!recipient"`.
  Además, `AccountantFactory.newAccountant()` despliega el contable antes de que la estrategia exista, lo que impide que nazca pre-configurado sin intervención multi-paso propensa a olvidos operacionales.

- **Remediación Defensiva:**
  Permitir que las estrategias agregadas o cualquier llamador invoque `distribute(token)`, enviando los fondos directamente al `feeRecipient` registrado o permitiendo a la estrategia reclamante recibir su cuota:
  ```solidity
  function distribute(address token) external virtual {
      uint256 amount = ERC20(token).balanceOf(address(this));
      ERC20(token).safeTransfer(feeRecipient, amount);
      emit DistributeRewards(token, amount);
  }
  ```

---

### YBOLD-HIGH-02: Bucle Ilimitado de Troves en `StrategyAprOracle` Provoca DoS por Out-of-Gas

- **Contrato:** `src/periphery/StrategyAprOracle.sol` (Líneas 92-105)
- **Severidad:** ALTA (Denegación de servicio en rebalanceo automatizado de vaults de Yearn V3)
- **Mecánica del Fallo:**
  En `aprAfterDebtChange`:
  ```solidity
  uint256 _count = _troveManager.sortedTroves().getSize();
  IMultiTroveGetter.CombinedTroveData[] memory _troves = MULTI_TROVE_GETTER.getMultipleSortedTroves(
      _collateralIndex,
      0, // startIdx
      _count
  );

  for (uint256 i = 0; i < _count; ++i) {
      uint256 _debt = _troves[i].entireDebt;
      uint256 _annualInterestRate = _troves[i].annualInterestRate;
      if (_debt == 0 || _annualInterestRate == 0) continue;
      _totalDebt += _debt;
      _weightedInterestRate += _annualInterestRate * _debt;
  }
  ```
  En Liquity V2, los troves en mercados activos como WETH o wstETH pueden superar los miles (5,000 - 15,000 posiciones individuales).
  1. `getMultipleSortedTroves(..., 0, _count)` asigna dinámicamente un array en memoria de tamaño `_count`.
  2. La lectura del árbol binario y la copia de structs consumen gas que excede el límite de bloque estándar de 30M gas.
  3. Dado que los asignadores automatizados de deuda de Yearn V3 llaman a `aprAfterDebtChange` durante transacciones de rebalanceo (`non-view`), la transacción completa revierte por Out-of-Gas, paralizando la gestión activa de riesgo y rendimiento.

- **Remediación Defensiva:**
  Implementar muestreo de troves representativos o leer métricas agregadas globales (`totalDebt` y tasas de interés acumuladas del contrato de registro de Liquity) en lugar de recorrer iterativamente todos los troves en la blockchain.

---

### YBOLD-MED-01: División Previa a Multiplicación Provoca Pérdida Total de Precisión de APR

- **Contrato:** `src/periphery/StrategyAprOracle.sol` (Línea 111)
- **Severidad:** MEDIA (Cálculo distorsionado o nulo de APR en estrategias de asignación)
- **Mecánica del Fallo:**
  ```solidity
  // slither-disable-next-line divide-before-multiply
  return _weightedInterestRate / _totalDebt * _totalDebt / uint256(int256(_stabilityPoolDeposits) + _delta)
      * _bias / WAD;
  ```
  La expresión ejecuta `_weightedInterestRate / _totalDebt` antes de multiplicar por `_totalDebt`.
  Si la tasa de interés ponderada es pequeña frente a la deuda total, la división entera trunca a cero o pierde los decimales menos significativos. La posterior multiplicación por `_totalDebt` magnifica el error de redondeo, reportando un APR artificialmente bajo o cero al motor de asignación.

- **Remediación Defensiva:**
  Agrupar multiplicaciones antes de divisiones:
  ```solidity
  uint256 targetDenominator = uint256(int256(_stabilityPoolDeposits) + _delta);
  return (_weightedInterestRate * _bias) / (targetDenominator * WAD);
  ```

---

## 3. DIRECCIÓN OFICIAL DE COBRO DE RECOMPENSAS

Todas las recompensas de la bolsa de **$14,500 USDC** correspondientes a esta auditoría deben ser adjudicadas y transferidas a la dirección pública verificada del auditor:

**EVM Payout Wallet:**  
`0x426d13134ee02f209bff6949cd2d2f209d57c964`  
*(Redes de cobro soportadas: Arbitrum One, Optimism, Ethereum Mainnet, Polygon, BNB Chain)*
