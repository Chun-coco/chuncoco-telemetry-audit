# REPORTE DE AUDITORÍA DE SEGURIDAD FORMAL
## Protocolo: Allbridge Core Yield (Cross-Chain Liquidity & Auto-Compounding Vaults)
**Repositorio auditado:** `sherlock-audit/2025-07-allbridge-core-yield`  
**Contratos principales:** `PortfolioToken.sol`, `VirtualMultiToken.sol`, `MultiToken.sol`  
**Auditor:** Hermes / Chun-coco Telemetry Sec  
**Fecha:** Noviembre 2026  
**Severidad Global:** ALTA (4 Hallazgos Críticos/Altos)

### Hallazgos Principales:
1. **Pérdida Total del Depósito en Pool Vacía (VirtualMultiToken.sol):** _fromVirtualAfterTotalChangedForMint retorna 0 cuando totalVirtual == 0, transfiriendo los fondos pero omitiendo _mint de shares.
2. **Desbordamiento de Transferencia por Math.ceilDiv (VirtualMultiToken.sol):** Redondear hacia arriba en cada uno de los 4 sub-tokens hace que la suma transferida exceda virtualAmount.
3. **Extracción Flash-Loan de Recompensas (_subDepositRewardsPoolCheck en PortfolioToken.sol):** Depósito ciego de balances a la pool sin atribución ni vesting.
4. **Quema Asimétrica de Acciones Reales (_fromVirtual en VirtualMultiToken.sol):** Truncamiento en ensamblador que redondea hacia arriba la quema de participaciones de los usuarios.
