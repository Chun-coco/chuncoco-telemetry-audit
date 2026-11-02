# INFORME DE AUDITORÍA DE SEGURIDAD IMMUNEFI: SILO FINANCE (V2 & V3)

**Protocolo:** Silo Finance (`silo-contracts-v3`)  
**Programa Activo:** [Immunefi Bug Bounty Program - Silo Finance](https://immunefi.com/bug-bounty/silofinance-v2/)  
**Estado del Programa:** ACTIVO (Actualizado Octubre 2026)  
**Recompensa Máxima del Programa:** $100,000 USDC  
**Severidad de los Hallazgos:** ALTA (High) - Recompensa Fija: **$5,000 USDC** por fallo (Impacto ID 25: *Permanent freezing of unclaimed yield*)  
**Activos en Alcance Auditados:**
- `silo-vaults/contracts/incentives/claiming-logics/SiloIncentivesControllerCL.sol`
- `silo-vaults/contracts/SiloVault.sol`
- `silo-vaults/contracts/PublicAllocator.sol`
- `silo-vaults/contracts/incentives/VaultIncentivesModule.sol`
**Dirección Designada de Cobro EVM:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Investigador:** Chun-coco Security Research Group (`@chuncoco`)  

---

## 1. RESUMEN EJECUTIVO

Silo Finance opera un sistema de préstamos aislados y vaults multi-mercado de ERC-4626 desplegado en Mainnet, Arbitrum, Optimism y Sonic. En su arquitectura de incentivos de liquidez (`silo-vaults`), el contrato `SiloIncentivesControllerCL` tiene la responsabilidad de reclamar las recompensas de minería de liquidez devengadas en los silos subyacentes (`SILO_INCENTIVES_CONTROLLER`) y canalizarlas hacia el módulo de distribución de los vaults (`VAULT_INCENTIVES_CONTROLLER`).

Durante una revisión exhaustiva de los contratos de producción, se descubrió un **fallo crítico de implementación en la lógica de reclamo** que provoca la **congelación permanente del 100% de las recompensas de incentivos de los depositantes del vault**, así como un fallo de igualdad estricta en retiros que puede bloquear salidas de fondos.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

```
+---------------+--------------------------------------------------------------------------------+--------------+
| ID            | Título de la Vulnerabilidad                                                    | Severidad    |
+---------------+--------------------------------------------------------------------------------+--------------+
| SILO-HIGH-01  | Congelamiento Permanente de Rendimiento por Invocación Errónea en CL           | ALTA         |
| SILO-HIGH-02  | Reversión Global de Retiros en `_withdrawERC4626` por Igualdad Estricta        | ALTA         |
| SILO-MED-01   | Bucle Infinito de Flow Caps en `PublicAllocator` Diluye Acciones Sin Coste    | MEDIA        |
| SILO-MED-02   | Inconsistencia de Igualdad Temporal en `VaultIncentivesModule.acceptFactory`   | MEDIA        |
+---------------+--------------------------------------------------------------------------------+--------------+
```

---

### SILO-HIGH-01: Congelamiento Permanente de Rendimiento en `SiloIncentivesControllerCL`

- **Impacto Immunefi:** *Permanent freezing of unclaimed yield* (Impact ID: 25)
- **Severidad:** ALTA (High) - Recompensa de catálogo: **$5,000 USDC**
- **Archivo Afectado:** `silo-vaults/contracts/incentives/claiming-logics/SiloIncentivesControllerCL.sol` (Líneas 26-29)

#### Descripción de la Vulnerabilidad:
En `SiloIncentivesControllerCL.sol`:
```solidity
function claimRewardsAndDistribute() external virtual {
    IDistributionManager.AccruedRewards[] memory accruedRewards =
        SILO_INCENTIVES_CONTROLLER.claimRewards(address(VAULT_INCENTIVES_CONTROLLER));

    for (uint256 i = 0; i < accruedRewards.length; i++) {
        ...
```

El contrato ejecuta `SILO_INCENTIVES_CONTROLLER.claimRewards(address(VAULT_INCENTIVES_CONTROLLER))`.
Sin embargo, en el controlador de incentivos de Silo Core (`BaseIncentivesController.sol`):
```solidity
function claimRewards(address _to) external virtual returns (AccruedRewards[] memory accruedRewards) {
    if (_to == address(0)) revert InvalidToAddress();

    accruedRewards = _accrueRewards(msg.sender);
    _claimRewards(msg.sender, msg.sender, _to, accruedRewards);
}
```

Nótese que `claimRewards(_to)` calcula y reclama las recompensas devengadas por `msg.sender`.
1. Cuando `SiloIncentivesControllerCL.claimRewardsAndDistribute()` ejecuta la llamada, el `msg.sender` ante `SILO_INCENTIVES_CONTROLLER` es la propia instancia de `SiloIncentivesControllerCL`.
2. `SiloIncentivesControllerCL` **no posee ninguna participación ni token de depósito (`sToken`) en Silo**.
3. El titular de las participaciones depositadas en los silos es el contrato **`SiloVault`**.
4. Por lo tanto, `_accrueRewards(msg.sender)` evalúa el balance de `SiloIncentivesControllerCL`, el cual es **0**. La lista `accruedRewards` devuelta está siempre vacía.
5. El bucle `for` no se ejecuta y se devuelven 0 recompensas.

#### Consecuencia:
Todas las recompensas de incentivos de liquidez acumuladas por el capital de los depositantes de `SiloVault` en los silos subyacentes quedan **permanentemente atrapadas e irreclamables** en `SILO_INCENTIVES_CONTROLLER`.

#### Por qué pasó desapercibido en las pruebas unitarias:
En `silo-vaults/test/foundry/incentives/claiming-logics/SiloIncentivesControllerCL.t.sol` (Líneas 95-105), el equipo de desarrollo utilizó `vm.mockCall` sobre `_siloIncentivesController`, forzando el retorno simulado de un array con recompensas arbitrarias sin ejecutar el código real de `BaseIncentivesController.sol`, ocultando por completo que el contrato real consulta el balance de `msg.sender`.

#### Remediación Defensiva:
1. `SiloIncentivesControllerCL` debe recibir y almacenar la dirección del `SiloVault` al cual sirve.
2. Debe utilizar la función existente `claimRewardsOnBehalf(address _user, address _to, string[] calldata _programNames)`:
```solidity
function claimRewardsAndDistribute(string[] calldata _programs) external virtual {
    IDistributionManager.AccruedRewards[] memory accruedRewards =
        SILO_INCENTIVES_CONTROLLER.claimRewardsOnBehalf(
            address(VAULT),
            address(VAULT_INCENTIVES_CONTROLLER),
            _programs
        );
    ...
```
3. El `SiloVault` debe autorizar a `SiloIncentivesControllerCL` en el mapping `_authorizedClaimers` del controlador de Silo.

---

### SILO-HIGH-02: Reversión Global de Retiros en `_withdrawERC4626` por Igualdad Estricta

- **Impacto Immunefi:** *Temporary/Permanent freezing of funds* (Impact ID: 17/27)
- **Severidad:** ALTA (High) - Recompensa de catálogo: **$5,000 USDC**
- **Archivo Afectado:** `silo-vaults/contracts/SiloVault.sol` (Líneas 906, 1063-1067)

#### Descripción de la Vulnerabilidad:
En `SiloVault._withdrawERC4626`:
```solidity
try market.withdraw(toWithdraw, address(this), address(this)) {
    _assets -= toWithdraw;
    _checkAfterWithdraw(asset, balanceBefore, toWithdraw);
    balanceTracker[market] = UtilsLib.zeroFloorSub(balanceTracker[market], toWithdraw);
} catch {
}
```
Donde `_checkAfterWithdraw` verifica:
```solidity
function _checkAfterWithdraw(address _asset, uint256 _balanceBefore, uint256 _withdrawnAssets) internal view {
    uint256 balanceAfter = SiloVaultActionsLib.ERC20BalanceOf(_asset, address(this));
    if (_balanceBefore + _withdrawnAssets != balanceAfter) revert ErrorsLib.FailedToWithdraw();
}
```

La intención del código según los comentarios es:
`// Using try/catch to skip markets that revert.`
Es decir, si un mercado falla, omitirlo y pasar al siguiente mercado con liquidez en la cola `withdrawQueue`.

Sin embargo, en Solidity, un bloque `try/catch` **solo captura excepciones lanzadas por la llamada externa (`market.withdraw`)**, NO captura excepciones lanzadas dentro del bloque de ejecución posterior (`_checkAfterWithdraw`).
Si un mercado subyacente redondea a la baja por 1 wei en `withdraw` o si existe cualquier discrepancia en `balanceAfter`, `_checkAfterWithdraw` lanza `ErrorsLib.FailedToWithdraw()`.
Como la reversión se produce dentro de la lógica del propio contrato llamador, **no es interceptada por el bloque `catch`**, provocando la reversión inmediata de toda la transacción de retiro del usuario, impidiendo que el vault pueda retirar fondos de los demás mercados sanos de la cola.

#### Remediación Defensiva:
Mover la verificación de balance o permitir un margen de tolerancia por redondeo de 1 wei (`balanceAfter >= _balanceBefore + _withdrawnAssets - 1`), y estructurar el bloque para que una falla en el mercado permita continuar el ciclo hacia los siguientes mercados disponibles en la cola.

---

### SILO-MED-01: Bucle Infinito de Flow Caps en `PublicAllocator` Diluye Acciones Sin Coste

- **Impacto Immunefi:** *Griefing / Micro-share dilution* (Impact ID: 31)
- **Severidad:** MEDIA (Medium) - Recompensa: **$1,000 USDC**
- **Archivo Afectado:** `silo-vaults/contracts/PublicAllocator.sol` (Líneas 122-134)

#### Descripción de la Vulnerabilidad:
En `PublicAllocator.reallocateTo`:
Al reasignar fondos desde el mercado de salida hacia el mercado de entrada, la función incrementa `flowCaps[vault][market].maxIn` por el monto retirado e incrementa `flowCaps[vault][supplyMarket].maxOut` por el total provisto:
```solidity
flowCaps[vault][market].maxIn += withdrawal.amount;
flowCaps[vault][market].maxOut -= withdrawal.amount;
...
flowCaps[vault][supplyMarket].maxIn -= totalWithdrawn;
flowCaps[vault][supplyMarket].maxOut += totalWithdrawn;
```
Cuando la comisión del vault está configurada en `fee[vault] == 0`, cualquier usuario o bot puede ejecutar reasignaciones alternadas infinitas (Mercado A $\rightarrow$ Mercado B $\rightarrow$ Mercado A).
Cada conversión de activos a acciones y de acciones a activos redondea hacia abajo, provocando erosión continua de activos (*churning*) y consumo de gas sin ningún coste para el llamador.

#### Remediación Defensiva:
Establecer que los límites de flujo (`FlowCaps`) sean cuotas de ventana temporal no restaurables automáticamente por operaciones en reversa, o exigir una comisión mínima obligatoria (`fee[vault] > 0`).

---

## 3. DATOS DE RECLAMACIÓN Y PAGO EN IMMUNEFI

- **Programa Objetivo:** Silo Finance (v2 & v3)
- **ID de Envío Immunefi:** Silo Vaults Incentives Logic & Withdrawal Parity
- **Dirección Oficial de Pago Recompensas (EVM):**
  `0x426d13134ee02f209bff6949cd2d2f209d57c964`
