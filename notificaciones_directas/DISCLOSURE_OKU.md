# SECURITY DISCLOSURE & BUG REPORT: OKU TRADE
**Target Protocol:** Oku Trade (Advanced Custom Order Types)  
**Target Contracts:** `contracts/automatedTrigger/Bracket.sol`, `contracts/automatedTrigger/OracleLess.sol`  
**Report Prepared By:** Chun-coco Telemetry Sec  
**Date:** November 2026  
**Security Contact Channel:** security@oku.trade / support@oku.trade / Discord (oku.trade)  
**Payout Address (USDC / Arbitrum / BSC / ETH):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Public Telemetry Repo:** https://github.com/Chun-coco/chuncoco-telemetry-audit/blob/master/REPORTE_AUDITORIA_SEGURIDAD_OKU.md

### Vulnerability Summary:
1. Critical/High: Concurrency Denial of Service (DoS) in performUpkeep (Order Fill Mismatch).
2. High: Global Bricking of Order Execution via verifyTokenBalances on rebasing tokens.
3. High/Medium: MEV Value Extraction via Arbitrary Keeper Swap Calldata.
4. Medium: Excess ETH Trapped in paysFee Modifier.
