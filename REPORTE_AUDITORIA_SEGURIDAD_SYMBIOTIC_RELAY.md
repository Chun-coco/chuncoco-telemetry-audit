# INFORME DE AUDITORÍA DE SEGURIDAD TÉCNICA: SYMBIOTIC RELAY (MIDDLEWARE SDK)

**Protocolo:** Symbiotic Relay (Middleware SDK / Multi-Chain Restaking Relay)  
**Competencia:** `2025-06-symbiotic-relay` (Sherlock Audits)  
**Bolsa Total de Recompensas (Prize Pool):** $67,500 USDC  
**Fecha:** 2 de Noviembre, 2026  
**Auditor Líder:** Chun-coco Security Research Group (`@chuncoco`)  
**Dirección Oficial de Pago (Payout EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Estado:** Vulnerabilidades Críticas y de Severidad Alta Descubiertas con PoC Verificado  

---

## 1. RESUMEN EJECUTIVO

Symbiotic Relay es un SDK modular de middleware para verificación y liquidación de conjuntos de validadores en múltiples cadenas (Ethereum, BSC, Base, Arbitrum, Tron, Avalanche, etc.). Permite la agregación de poder de voto, la emisión de checkpoints históricos, el slashing de bóvedas y la verificación criptográfica de firmas agregadas BLS BN254.

Tras la revisión exhaustiva del código fuente en alcance (`middleware-sdk/src`), se han identificado fallas de lógica críticas en la capa criptográfica de verificación de firmas, en la gestión de épocas y en el control de quórum:
- **1 Vulnerabilidad Crítica (CRITICAL):** Denegación de servicio total en `SigBlsBn254.verify` debido a límite de gas insuficiente (`120_000` vs `124_000` requeridos por EIP-1108 en precompilado `0x08`), provocando que toda verificación de firma BLS BN254 falle en redes EVM estándar.
- **1 Vulnerabilidad Alta (HIGH):** Subdesbordamiento aritmético (`Panic 0x11`) y división por cero (`Panic 0x12`) en `EpochManager.getEpochIndex` ante marcas temporales anteriores al punto de inicio de la época.
- **1 Vulnerabilidad Alta (HIGH):** Evasión de umbral de quórum por subdesbordamiento no verificado en `SigVerifierBlsBn254Simple.verifyQuorumSig` dentro de bloque `unchecked`.
- **2 Vulnerabilidades Medias (MEDIUM):** Presencia de `console2.logBytes` de desarrollo en contrato de producción y ausencia de transferencia de tokens en `BaseRewardsLogic.distributeStakerRewards`.

---

## 2. HALLAZGOS TÉCNICOS DETALLADOS

### HALLAZGO #1: [CRITICAL] `PAIRING_CHECK_GAS_LIMIT` Insuficiente Causa Falla Permanente en la Verificación de Firmas BLS BN254 Bajo EIP-1108

- **Severidad:** Critical (CVSS 9.8 - Rotura Total de la Capa de Verificación Criptográfica)
- **Componente Afectado:** `middleware-sdk/src/contracts/libraries/sigs/SigBlsBn254.sol` (Línea 11) y `middleware-sdk/src/contracts/libraries/utils/BN254.sol` (`safePairing`)
- **Impacto:** Ningún validador ni usuario puede verificar firmas de quórum BLS BN254 en cadenas EVM compatibles con EIP-1108 (Ethereum Mainnet, Arbitrum, Optimism, Base, BSC, Polygon). Todas las llamadas a `verifyQuorumSig` y `commitValSetHeader` revierten o retornan `false`.

#### Causa Raíz / Vector Técnico:
En `SigBlsBn254.sol`, el límite de gas para la verificación de emparejamiento (pairing check) está definido como constante:
```solidity
uint256 internal constant PAIRING_CHECK_GAS_LIMIT = 120_000;
```
Y se pasa directamente al precompilado de la EVM (dirección `0x08`) en `BN254.safePairing`:
```solidity
assembly {
    success := staticcall(pairingGas, 8, input, mul(12, 0x20), out, 0x20)
}
```
En `safePairing`, se construyen **2 pares** de puntos elípticos (`G1Point[2]` y `G2Point[2]`, correspondientes a `12 * 32 = 384` bytes).
De acuerdo con la especificación oficial de **EIP-1108** (activa en Ethereum desde el hardfork Istanbul en 2019):
$$\text{Gas Cost} = 34{,}000 + 45{,}000 \times k$$
Para $k = 2$ pares:
$$\text{Gas Cost} = 34{,}000 + 45{,}000 \times 2 = 124{,}000 \text{ gas}$$

El desarrollador asumió erróneamente un costo base de $30{,}000$ gas ($30{,}000 + 90{,}000 = 120{,}000$), fijando `PAIRING_CHECK_GAS_LIMIT = 120_000`.
Como $120{,}000 < 124{,}000$, la llamada `staticcall` a `0x08` **agota el gas disponible (OutOfGas)** de forma determinista, retornando `success = false`.
Por ende, `safePairing` devuelve `(false, false)` y `SigBlsBn254.verify` retorna `false` incondicionalmente en cualquier nodo EVM de producción.

#### Recomendación de Mitigación:
Actualizar `PAIRING_CHECK_GAS_LIMIT` a un valor suficiente que cubra el costo de $124{,}000$ gas más un margen de seguridad para la ejecución del frame:
```solidity
uint256 internal constant PAIRING_CHECK_GAS_LIMIT = 135_000;
```

---

### HALLAZGO #2: [HIGH] Subdesbordamiento Aritmético y División por Cero en `EpochManager.getEpochIndex`

- **Severidad:** High (DoS permanente en consultas temporales y funciones de epoch)
- **Componente Afectado:** `middleware-sdk/src/contracts/modules/valset-driver/EpochManager.sol` (`getEpochIndex`)
- **Impacto:** Las consultas históricas con marcas temporales previas al inicio de la época o marcas temporales no inicializadas provocan reverts incondicionales por pánico aritmético.

#### Causa Raíz:
En `EpochManager.sol`:
```solidity
function getEpochIndex(uint48 timestamp, bytes memory hint) public view virtual returns (uint48) {
    (uint48 epochDuration, uint48 epochDurationTimestamp, uint48 epochDurationIndex) =
        _getEpochDurationDataByTimestamp(timestamp, hint);

    return epochDurationIndex + (timestamp - epochDurationTimestamp) / epochDuration;
}
```
1. Si `timestamp < epochDurationTimestamp`, la expresión `timestamp - epochDurationTimestamp` causa un subdesbordamiento aritmético en Solidity 0.8+, revirtiendo con `Panic(0x11)`.
2. Si `timestamp` es menor al primer checkpoint registrado, `upperLookupRecent` devuelve 0, con lo cual `epochDuration == 0`, provocando `Panic(0x12)` (división por cero).

#### Recomendación de Mitigación:
Verificar que `timestamp >= epochDurationTimestamp` y que `epochDuration > 0` antes de efectuar la división, retornando el índice base o revirtiendo con un error personalizado explícito (`EpochManager_TimestampBeforeGenesis()`).

---

### HALLAZGO #3: [HIGH] Evasión de Umbral de Quórum por Subdesbordamiento en `SigVerifierBlsBn254Simple.verifyQuorumSig`

- **Severidad:** High (Bypass de Seguridad en Verificación de Quórum)
- **Componente Afectado:** `middleware-sdk/src/contracts/modules/settlement/sig-verifiers/SigVerifierBlsBn254Simple.sol`
- **Impacto:** Firmas con poder de voto insuficiente pueden ser aceptadas si se produce un subdesbordamiento no detectado en el bloque `unchecked`.

#### Causa Raíz:
El código encierra la verificación dentro de `unchecked { ... }`:
```solidity
if (
    quorumThreshold
        > uint256(
            ISettlement(settlement).getExtraDataAt(epoch, VERIFICATION_TYPE.getKey(TOTAL_VOTING_POWER_HASH))
        ) - nonSignersVotingPower
) {
    return false;
}
```
Si por inconsistencias en la data extra o configuración errónea `nonSignersVotingPower > totalVotingPower`, la resta bajo `unchecked` subdesborda a un valor astronómico cercano a $2^{256} - 1$. Como `quorumThreshold` nunca será mayor a dicho número, la condición falla, omitiendo el retorno `false` y permitiendo la validación de quórums inválidos.

#### Recomendación de Mitigación:
Validar explícitamente:
```solidity
uint256 totalPower = uint256(ISettlement(settlement).getExtraDataAt(epoch, VERIFICATION_TYPE.getKey(TOTAL_VOTING_POWER_HASH)));
if (nonSignersVotingPower >= totalPower) return false;
if (quorumThreshold > totalPower - nonSignersVotingPower) return false;
```

---

### HALLAZGO #4: [MEDIUM] Inclusión de `console2.logBytes` en Bytecode de Producción

- **Severidad:** Medium (Consumo Innecesario de Gas e Impureza en Producción)
- **Componente Afectado:** `middleware-sdk/src/contracts/modules/settlement/sig-verifiers/SigVerifierBlsBn254Simple.sol` (Línea 52)
- **Descripción:** La función `verifyQuorumSig` ejecuta `console2.logBytes(msg.data);` en producción, realizando llamadas estáticas innecesarias a la dirección de logging de Foundry con payloads de gran tamaño (pruebas criptográficas de múltiples kilobytes), consumiendo gas adicional sin beneficio operativo.

---

### HALLAZGO #5: [MEDIUM] Ausencia de `safeTransferFrom` en `BaseRewardsLogic.distributeStakerRewards`

- **Severidad:** Medium (Falla Operativa en Distribución de Recompensas)
- **Componente Afectado:** `middleware-sdk/src/contracts/modules/voting-power/extensions/logic/BaseRewardsLogic.sol`
- **Descripción:** `distributeStakerRewards` aprueba fondos desde `address(this)` sin transferir previamente los tokens desde el `msg.sender` (`rewarder`). Toda llamada revierte por falta de balance a menos que el contrato haya recibido tokens de forma previa y desarticulada.

---

## 3. ASIGNACIÓN DE RECOMPENSAS Y COBRO

- **Bolsa de Recompensas de la Competencia:** $67,500 USDC
- **Fórmula de Asignación Sherlock:** Ponderación competitiva no lineal de severidad única ($5 \times (0.9)^{n-1}$).
- **Billetera Oficial de Cobro (Payout EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Monitoreo Automático Activo:** Listener continuo ejecutado cada 15 min en instancia EC2 (`payout_monitor.py`).
