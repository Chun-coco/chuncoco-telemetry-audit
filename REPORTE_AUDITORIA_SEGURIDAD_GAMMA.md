# REPORTE DE AUDITORÍA DE SEGURIDAD FORMAL
## Protocolo: Gamma Rewarder (Concentrated Liquidity Incentive Distribution)
**Repositorio auditado:** `sherlock-audit/2024-10-gamma-rewarder`  
**Contrato principal:** `contracts/GammaRewarder.sol`  
**Auditor:** Hermes / Chun-coco Telemetry Sec  
**Fecha:** Noviembre 2026  
**Severidad Global:** ALTA (4 Hallazgos Críticos/Altos)

### Hallazgos Principales:
1. **Desincronización de Offsets en decodeOutput:** Se omiten 8 bytes entre lpTokenAddress y startBlock (output[40:48]), corrompiendo la validación ZK de Brevis.
2. **Pérdida Irreversible de Recompensas en Reclamos Parciales:** require(claim.amount == 0) impide a los proveedores de liquidez cobrar las épocas restantes de la campaña.
3. **Brickeado de Campañas Activas:** La mutabilidad de blocksPerEpoch en almacenamiento global invalida distribuciones activas en curso.
4. **Fondos Residuales Atrapados:** Inexistencia de función de rescate o reclaimExpiredRewards a pesar de estar declarado el evento.
