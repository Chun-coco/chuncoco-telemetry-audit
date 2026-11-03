# BUG BOUNTY DISCLOSURE: PENDLE FINANCE (CORE V2)
**Program:** Pendle Finance Core Security Audit & Bug Bounty  
**Max Bounty Pool:** $500,000 USDC  
**Report Date:** November 03, 2026  
**Auditor / Submitter:** Chuncoco Telemetry & Security Engine  
**Designated Bounty Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  

---

## 1. TARGET ASSET & REPOSITORY DETAILS
- **Project Name:** Pendle Finance
- **Repository:** `https://github.com/pendle-finance/pendle-core-v2-public`
- **Scope / Module:** `contracts/core/YieldContracts/` & `contracts/core/Market/`
- **Impacted Contracts:**
  - `InterestManagerYT.sol`
  - `PendleYieldToken.sol`
  - `PendleMarketV7.sol`

---

## 2. VULNERABILITY SUMMARY

### Vulnerability 1: Critical Panic(0x11) Underflow via Negative Slashing Index in `InterestManagerYT`
- **Severity:** Critical
- **Vulnerability Type:** Permanent Denial of Service / Fund Lockup
- **Location:** `contracts/core/YieldContracts/InterestManagerYT.sol#L77-L83`
- **Summary:**
  `InterestManagerYT._distributeInterestPrivate` performs `uint256 interestFromYT = (principal * (currentIndex - prevIndex)).divDown(...)`. In modern DeFi, liquid staking (LSTs) and restaking tokens (LRTs) can suffer negative index adjustments due to validator slashing or depeg events (`currentIndex < prevIndex`). In Solidity 0.8.17, `currentIndex - prevIndex` underflows unconditionally with a Panic(0x11). Because `_distributeInterest` is called on every YT transfer, mint, burn, and redemption, a single negative yield shock permanently bricks all operations in the affected Pendle market.

### Vulnerability 2: Treasury Transfer Reversion Freezing User Yield Claims
- **Severity:** Medium
- **Vulnerability Type:** Coupled Execution Denial of Service
- **Location:** `contracts/core/YieldContracts/InterestManagerYT.sol#L45-L62`
- **Summary:**
  `_doTransferOutInterest` pushes fee transfers to `treasury` atomically with user interest transfers. Any failure or restriction on the treasury address reverts the transaction, preventing users from claiming their earned yield.

---

## 3. PROPOSED REMEDIATIONS
1. **Handle Negative Yield Non-Underflow:** Clamp `if (currentIndex <= prevIndex) { userInterest[user].index = currentIndex.Uint128(); return; }` to prevent contract halts during negative yield shocks.
2. **Decouple Protocol Fee Extraction:** Accrue protocol fees in storage for pull-based withdrawal by governance rather than pushing tokens inline.

---

## 4. FORMAL PAYOUT DESIGNATION
- **EVM Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Preferred Token:** USDC
