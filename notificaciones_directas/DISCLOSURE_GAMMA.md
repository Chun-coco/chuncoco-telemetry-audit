# SECURITY DISCLOSURE & BUG REPORT: GAMMA STRATEGIES
**Target Protocol:** Gamma Strategies  
**Target Contract:** `contracts/GammaRewarder.sol`  
**Report Prepared By:** Chun-coco Telemetry Sec  
**Date:** November 2026  
**Security Contact Channel:** security@gamma.xyz / Immunefi Bug Bounty (gammastrategies)  
**Payout Address (USDC / Arbitrum / BSC / ETH):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Public Telemetry Repo:** https://github.com/Chun-coco/chuncoco-telemetry-audit/blob/master/REPORTE_AUDITORIA_SEGURIDAD_GAMMA.md

### Vulnerability Summary:
1. Critical/High: Byte Offset Desynchronization in decodeOutput Corrupting Brevis ZK Verification.
2. High: Permanent Forfeiture of Rewards on Incremental / Partial Claims.
3. High: Bricking of Active Distributions by Mutable blocksPerEpoch Storage Variable.
4. Medium: Permanent Trapping of Unclaimed Residuals and Truncation Dust.
