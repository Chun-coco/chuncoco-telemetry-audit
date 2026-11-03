# DIVULGACIÓN TÉCNICA RESPONSABLE: MORPHO BLUE (IMMUNEFI BUG BOUNTY)
**Protocolo:** Morpho Blue (`morpho-blue`)  
**Fecha:** 3 de Noviembre de 2026  
**Severidad Propuesta:** High  
**Bolsa del Programa:** $2,500,000 USDC  
**Beneficiario de Recompensa (EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`

### Resumen del Problema
1. Truncamiento de comisiones del protocolo (`feeShares`) a cero en micro-intervalos de tiempo por división entera sin residuo.
2. Distorsión de ratio de acciones virtuales en mercados con tokens de pocos decimales (GUSD, EURS).
3. Inconsistencia de balances transitorios expuestos a contratos integradores durante el callback `onMorphoLiquidate`.

### Estado de Remediación
Código verificado en `Morpho.sol` y `MorphoBalancesLib.sol`. Remediaciones recomendadas documentadas detalladamente.

**Dirección de Payout:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
