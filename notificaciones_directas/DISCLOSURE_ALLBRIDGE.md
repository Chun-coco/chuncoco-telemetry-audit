# SECURITY DISCLOSURE & BUG REPORT: ALLBRIDGE
**Target Protocol:** Allbridge Core Yield  
**Target Contracts:** `contracts/VirtualMultiToken.sol`, `contracts/PortfolioToken.sol`  
**Report Prepared By:** Chun-coco Telemetry Sec  
**Date:** November 2026  
**Security Contact Channel:** security@allbridge.io / Immunefi Bug Bounty (allbridge)  
**Payout Address (USDC / Arbitrum / BSC / ETH):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Public Telemetry Repo:** https://github.com/Chun-coco/chuncoco-telemetry-audit/blob/master/REPORTE_AUDITORIA_SEGURIDAD_ALLBRIDGE.md

### Vulnerability Summary:
1. Critical: 100% Loss of Deposited Funds on Empty Pools in VirtualMultiToken.sol.
2. High: MultiToken Transfer Outflow Exceeding virtualAmount via Math.ceilDiv.
3. High: Flash-Loan Reward Extraction via Unattributed Balance Deposits in PortfolioToken.sol.
