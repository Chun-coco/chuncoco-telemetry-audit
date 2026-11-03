# BUG BOUNTY DISCLOSURE: LIDO CORE (WITHDRAWAL QUEUE)
**Program:** Lido Bug Bounty Program (Immunefi)  
**Program URL:** `https://immunefi.com/bug-bounty/lido/`  
**Max Bounty Pool:** $2,000,000 USD (USDC / DAI / USDT)  
**Report Date:** November 03, 2026  
**Auditor / Submitter:** Chuncoco Telemetry & Security Engine  
**Designated Bounty Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  

---

## 1. TARGET ASSET & REPOSITORY DETAILS
- **Project Name:** Lido Core
- **Repository:** `https://github.com/lidofinance/core`
- **Scope / Module:** `contracts/0.8.9/WithdrawalQueue.sol`
- **Impacted Contracts:**
  - `WithdrawalQueue.sol`
  - `WithdrawalQueueBase.sol`

---

## 2. VULNERABILITY SUMMARY

### Vulnerability 1: Unbounded Checkpoint Hint Search Out-of-Gas DoS in `WithdrawalQueue.claimWithdrawal`
- **Severity:** Medium-High
- **Vulnerability Type:** Denial of Service / Block Gas Limit Exhaustion
- **Location:** `contracts/0.8.9/WithdrawalQueue.sol#L277-L287`
- **Summary:**
  `claimWithdrawal(_requestId)` executes an unbounded linear or binary scan via `_findCheckpointHint(_requestId, 1, getLastCheckpointIndex())`. As cumulative oracle checkpoints expand into thousands, gas consumption surpasses the block gas limit, rendering single-request direct claims permanently uncallable for users and integrated protocols.

---

## 3. PROPOSED REMEDIATIONS
1. **Deprecate Unbounded Scans:** Deprecate `claimWithdrawal(_requestId)` without hints, requiring caller-provided checkpoint hints (`claimWithdrawals`).

---

## 4. FORMAL PAYOUT DESIGNATION
- **EVM Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Preferred Token:** USDC, USDS, DAI, or USDT
