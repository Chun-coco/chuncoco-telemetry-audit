# SECURITY DISCLOSURE & BUG REPORT: TELCOIN
**Target Protocol:** Telcoin Platform  
**Target Contracts:** `contracts/AmirX.sol`, `contracts/stablecoin/StablecoinHandler.sol`  
**Report Prepared By:** Chun-coco Telemetry Sec  
**Date:** November 2026  
**Security Contact Channel:** security@telcoin.org / Immunefi Bug Bounty  
**Payout Address (USDC / Arbitrum / BSC / ETH):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Public Telemetry Repo:** https://github.com/Chun-coco/chuncoco-telemetry-audit/blob/master/REPORTE_AUDITORIA_SEGURIDAD_TELCOIN.md

### Vulnerability Summary:
1. Critical: MEV Sandwich Exploitation in AmirX._buyBack() via Unbounded Dynamic Aggregator Calls.
2. High: Permanent Denial of Service (DoS) in AmirX Mint & Burn due to Strict Blacklist Invariants.
3. Medium: Integer Underflow Boundary Revert instead of InvalidMintBurnBoundry Custom Error.
