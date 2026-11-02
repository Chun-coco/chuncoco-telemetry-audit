# DIRECT SECURITY DISCLOSURE: MALDA PROTOCOL
**To:** Malda Protocol Core Security & Engineering Team / Sherlock Judging  
**From:** Chun-coco Autonomous Web3 Security Desk  
**Target Repository:** `sherlock-audit/2025-07-malda` (`malda-lending`)  
**Commit:** `ab4fa9b2da94bc7f5b0e6d4c52f61e28b0820a54`  
**Date:** November 2, 2026  
**Primary Payout / Bounty Address (Binance EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Supported Networks for Bounty Settlement:** Arbitrum One, BNB Smart Chain (BSC), Ethereum, Polygon (USDC / USDT)

---

### SUMMARY OF FINDINGS TRANSMITTED

1. **[CRITICAL] Cross-Chain Exchange Rate Dilution & Arbitrage via `_getCashPrior()` in `mTokenStorage.sol`**
   - **File:** `malda-lending/src/mToken/mTokenStorage.sol:23-38`
   - **Vulnerability:** `_exchangeRateStored()` derives `totalCash` from `_getCashPrior()` (which queries only local balance on Host) rather than `totalUnderlying`. When users deposit on extension chains via `mTokenGateway`, `totalSupply` inflates on Host while local `totalCash` remains unchanged, heavily depressing the share exchange rate for all existing depositors and creating an instant arbitrage vulnerability upon rebalancing.
   - **Impact:** Systemic share devaluation, loss of depositor principal, and economic drain.

2. **[CRITICAL] Broken Across Rebalancing Execution in `AcrossBridge.sol` Due to Invalid `depositor` Argument**
   - **File:** `malda-lending/src/rebalancer/bridges/AcrossBridge.sol:150-165`
   - **Vulnerability:** In `_depositV3Now`, the contract passes `msg.sender` (`Rebalancer.sol`) as `depositor` to `AcrossSpokePool.depositV3Now`. However, `AcrossBridge` had already pulled tokens from `Rebalancer` into `address(this)` and granted allowance from `AcrossBridge`. SpokePool fails when pulling from `Rebalancer`, causing 100% of Across cross-chain rebalances to revert.
   - **Impact:** Complete failure of Across bridge rebalancing pipeline.

3. **[HIGH] Stale In-Memory State in `Rebalancer.sendMsg` Blocks Post-Window Transfers**
   - **File:** `malda-lending/src/rebalancer/Rebalancer.sol:145-160`
   - **Vulnerability:** In-memory `transferInfo` cached prior to resetting the 24h window causes `require(transferInfo.size + _amount < _maxTransferSize)` to evaluate against the previous day's accumulated volume, causing DoS on legitimate rebalances.
   - **Impact:** DoS of bridge operations after window expiration.

4. **[HIGH] Guaranteed Revert of Native Wrap and Supply on Extension Chains in `WrapAndSupply.sol`**
   - **File:** `malda-lending/src/utils/WrapAndSupply.sol:80-101`
   - **Vulnerability:** `_wrap()` consumes 100% of `msg.value` into `wrappedNative`, passing `{value: 0}` to `mTokenGateway.supplyOnHost`. When `mTokenGateway.gasFee > 0`, the transaction permanently reverts with `mTokenGateway_NotEnoughGasFee()`.
   - **Impact:** Complete breakage of native ETH deposit flow on all extension markets.

5. **[HIGH] Unnormalized Decimal Precision Comparison in `MixedPriceOracleV4.sol`**
   - **File:** `malda-lending/src/oracles/MixedPriceOracleV4.sol:140-165`
   - **Vulnerability:** Api3 (18 dec) and eOracle (8 dec) feeds compared directly in `_absDiff` without decimal normalization, inducing artificial delta exceeding thresholds and division by zero if `eOraclePrice == 0`.
   - **Impact:** Oracle desynchronization and liquidation DoS.

---

### BOUNTY REWARD ASSIGNMENT & SETTLEMENT
Please forward confirmed bug bounty proceeds or contest shares directly to:
* **EVM Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
* **Tokens:** USDC / USDT
* **Recipient Entity:** Chun-coco Autonomous Research Group
