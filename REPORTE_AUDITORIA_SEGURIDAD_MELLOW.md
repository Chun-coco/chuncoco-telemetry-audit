# REPORTE DE AUDITORÍA DE SEGURIDAD FORMAL
## Protocolo: Mellow Flexible Vaults (Liquid Restaking & Modular Yield Vaults)
**Repositorio auditado:** `sherlock-audit/2025-07-mellow-flexible-vaults`  
**Contratos principales:** `src/managers/FeeManager.sol`, `src/queues/DepositQueue.sol`, `src/vaults/Vault.sol`  
**Auditor:** Hermes / Chun-coco Telemetry Sec  
**Fecha:** Noviembre 2026  
**Severidad Global:** ALTA (4 Hallazgos Críticos/Altos)

### Hallazgos Principales:
1. **Inversión Lógica en el Cálculo de Performance Fee (FeeManager.sol):** Rastrear minPriceD18 y calcular minPrice - priceD18 cobra comisiones sobre pérdidas durante caídas y nunca cobra comisiones por ganancias.
2. **Corrupción del Árbol Fenwick en Cancelaciones (DepositQueue.sol):** Uso del índice de prices.latestCheckpoint() en vez del índice original de timestamps corrompe la suma prefija de depósitos pendientes.
3. **Dilución de Shares Iniciales (First Deposit Inflation en Subvault.sol):** Posibilidad de inflar el precio por share donando activos antes de la primera emisión pública.
4. **Asimetría de Redondeo en calculateRedeemFee:** Truncamiento hacia abajo en salida de shares puede bloquear el retiro del último usuario de la bóveda.
