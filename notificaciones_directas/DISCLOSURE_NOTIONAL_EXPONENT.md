# DIRECT VULNERABILITY DISCLOSURE & PAYOUT ROUTING

**Target Protocol:** Notional Exponent (Notional V4)  
**Contest Identifier:** `2025-06-notional-exponent` (Sherlock Audits)  
**Total Reward Pool:** $75,500 USDC  
**Submission Auditor:** Chun-coco Security Research Group (`@chuncoco`)  
**Designated EVM Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
*(Supported networks: Arbitrum One, Optimism, Ethereum Mainnet, Polygon, BNB Chain)*  

---

## Findings Summary

1. **[CRITICAL] Permanent User Capital Freeze via Reverting `PendlePTLib.redeemExpiredPT`:**
   - **File:** `notional-v4/src/staking/PendlePTLib.sol` (Line 72)
   - **Root Cause:** Invocation of `yt.redeemPY` requires burning equal YT balance from the caller. The vault holds zero YT, causing all post-maturity withdrawals to revert permanently.
   - **Impact:** 100% of user principal in expired Pendle PT vaults is irretrievable.

2. **[HIGH] Position Entry Failure in `MorphoLendingRouter.onMorphoFlashLoan`:**
   - **File:** `notional-v4/src/routers/MorphoLendingRouter.sol` (Line 104)
   - **Root Cause:** Calling `MORPHO.borrow` without verified delegation or signature authorization reverts with `"not authorized"`.

3. **[MEDIUM] Intermediate Swap Slippage Vulnerability in `PendlePTLib.swapExactPtForToken`:**
   - **File:** `notional-v4/src/staking/PendlePTLib.sol`
   - **Root Cause:** Hardcoding `tokenOutput.minTokenOut = 0` creates MEV sandwich exposure.

4. **[MEDIUM] Chainlink Sequencer Feed Missing for L2 Deployments:**
   - **File:** `notional-v4/src/oracles/Curve2TokenOracle.sol`

---

## Payout Destination
All bounty allocations, rewards, and judging disbursements for this submission MUST be credited directly to the official payout wallet:
`0x426d13134ee02f209bff6949cd2d2f209d57c964`
