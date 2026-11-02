# REPORTE DE AUDITORÍA DE SEGURIDAD FORMAL
## Protocolo: Oku Trade (Advanced Order Types on Uniswap v3)
**Repositorio auditado:** `sherlock-audit/2025-07-oku-trade-order-types`  
**Contratos principales:** `Bracket.sol`, `OracleLess.sol`, `AutomationMaster.sol`  
**Auditor:** Hermes / Chun-coco Telemetry Sec  
**Fecha:** Noviembre 2026  
**Severidad Global:** ALTA (4 Hallazgos Críticos/Altos)

### Hallazgos Principales:
1. **Denegación de Servicio en Ejecución Concurrente (Bracket.sol):** Requiring orderId == dataSet.at(pendingOrderIdx) provoca reversiones generalizadas ("Order Fill Mismatch") cuando el swap-and-pop de EnumerableSet altera los índices en ejecuciones simultáneas.
2. **Bloqueo Global de Órdenes por Tokens de Rebase (Bracket.sol:695):** La verificación O(N) de balances sobre todos los tokens registrados revierte toda orden si un solo token sufre rebase o transferencia.
3. **Explotación MEV en Calldata Arbitraria:** Bypasses de slippage en target.call(txData).
4. **Pérdida de Excedentes de ETH en paysFee:** msg.value excedente queda atrapado sin reembolso.
