# SECURITY DISCLOSURE & BUG REPORT: MELLOW PROTOCOL
**Target Protocol:** Mellow Protocol (Flexible Vaults)  
**Target Contracts:** `src/managers/FeeManager.sol`, `src/queues/DepositQueue.sol`  
**Report Prepared By:** Chun-coco Telemetry Sec  
**Date:** November 2026  
**Security Contact Channel:** security@mellow.finance  
**Payout Address (USDC / Arbitrum / BSC / ETH):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Public Telemetry Repo:** https://github.com/Chun-coco/chuncoco-telemetry-audit/blob/master/REPORTE_AUDITORIA_SEGURIDAD_MELLOW.md

### Vulnerability Summary:
1. Critical: Inverted High Water Mark Logic in FeeManager.sol (Charges Fees on Drawdown Losses & Zero Fees on Gains).
2. High: Fenwick Tree Prefix-Sum Desynchronization on Deposit Cancellations (DepositQueue.sol).
3. Medium/High: First-Deposit Share Inflation Dilution in Subvault.sol.
