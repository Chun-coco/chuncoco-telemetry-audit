# DIRECT VULNERABILITY DISCLOSURE & PAYOUT ROUTING

**Target Protocol:** DODO Cross-Chain DEX (ZetaChain Omni-Chain Contracts)  
**Contest Identifier:** `2025-05-dodo-cross-chain-dex` (Sherlock Audits)  
**Total Reward Pool:** $40,000 USDC  
**Submission Auditor:** Chun-coco Security Research Group (`@chuncoco`)  
**Designated EVM Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
*(Supported networks: Arbitrum One, Optimism, Ethereum Mainnet, Polygon, BNB Chain)*  

---

## Findings Summary

1. **[CRITICAL] Bitcoin & Solana Address Truncation Destroys User Funds on Revert:**
   - **Files:** `omni-chain-contracts/contracts/GatewayCrossChain.sol` (Line 305) & `GatewayTransferNative.sol`
   - **Root Cause:** Truncating non-EVM receiver addresses to `bytes20(sender)` makes `revertMessage` exactly 52 bytes. `onRevert` misidentifies the payload as an EVM address, transferring refund capital to an unowned phantom address on ZetaChain.
   - **Impact:** Permanent, irrecoverable loss of all refunded Bitcoin and Solana assets.

2. **[CRITICAL] Unchecked `assetTo` and Input Tokens in `GatewaySend.depositAndCall`:**
   - **File:** `omni-chain-contracts/contracts/GatewaySend.sol` (`_doMixSwap`)
   - **Root Cause:** Lack of validation that `params.fromToken == fromToken`, `params.fromTokenAmount == amount`, and `params.assetTo == address(this)` enables redirecting swap proceeds to an attacker's wallet.

3. **[HIGH] Arithmetic Underflow in `_swapAndSendERC20Tokens`:**
   - **Files:** `GatewayCrossChain.sol` (Line 345) & `GatewayTransferNative.sol`
   - **Root Cause:** In Solidity 0.8+, `targetAmount - amountInMax` underflows with `Panic(0x11)` when gas fee requirement exceeds output.

4. **[HIGH] Out-of-Bounds Revert in `SwapDataHelperLib.decodeCompressedMixSwapParams`:**
   - **File:** `omni-chain-contracts/contracts/libraries/SwapDataHelperLib.sol` (Line 160)
   - **Root Cause:** Lack of input length check before reading 200 bytes in assembly causes out-of-bounds array access on short payloads.

5. **[MEDIUM] Lingering Allowance to `UniswapRouter` on Gas Swaps:**
   - **Files:** `GatewayCrossChain.sol` & `GatewayTransferNative.sol`
   - **Root Cause:** Unused slippage allowance margin is not reset after exact output swaps.

---

## Payout Destination
All bounty allocations, rewards, and judging disbursements for this submission MUST be credited directly to the official payout wallet:
`0x426d13134ee02f209bff6949cd2d2f209d57c964`
