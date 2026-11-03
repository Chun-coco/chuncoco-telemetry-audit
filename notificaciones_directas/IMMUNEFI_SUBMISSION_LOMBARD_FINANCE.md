# IMMUNEFI BUG BOUNTY DISCLOSURE: LOMBARD FINANCE
**Target:** Lombard Finance (`lombard-finance`)  
**Program URL:** https://immunefi.com/bug-bounty/lombard-finance/  
**Repository:** https://github.com/lombard-finance/evm-smart-contracts (Commit: `7fe83e5`)  
**Severity:** High  
**Vulnerability Type:** Unprotected Entry Point / Fee Circumvention / DoS on NAV Reconciliation  
**Researcher Designated Payout Address (EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
(Networks: Arbitrum, Optimism, Ethereum Mainnet, Base, Sonic, Polygon)

---

## 1. Vulnerability Summary
Two primary security defects were discovered in Lombard Finance's EVM production contracts:

1. **Protocol Fee Circumvention & Claimer Frontrunning in `AssetRouter.sol`:**
   `AssetRouter.sol` exposes an unpermissioned `mint(bytes rawPayload, bytes proof)` function. When authorized claimers broadcast `mintWithFee` to collect approved user fees for themselves and the protocol treasury, frontrunning bots can extract `(rawPayload, proof)` and execute `AssetRouter.mint` directly, consuming the proof in `handlePayload` without paying fees and causing the claimer's transaction to revert.

2. **Denial of Service in `StrategyBaseUpgradeable.postPricePerShare`:**
   In `postPricePerShare`, mid-epoch redemption fulfillment decrements `_effectiveShareSupply()`. If redemptions occur after the off-chain NAV snapshot, `removalValue` calculated at `oldPps` can exceed `scaled`, triggering a revert with `Strategy_InsufficientNavForReconciliation` and completely freezing NAV updates.

---

## 2. Proof of Concept (PoC)

### PoC 1: Fee Circumvention via `AssetRouter.mint`
1. User requests a deposit and signs a fee authorization `feePayload` with signature `userSignature`.
2. Authorized claimer submits:
   ```solidity
   assetRouter.mintWithFee(mintPayload, proof, feePayload, userSignature);
   ```
3. An attacker/recipient observes the transaction in the public mempool.
4. Attacker submits:
   ```solidity
   assetRouter.mint(mintPayload, proof);
   ```
   with higher priority gas.
5. In `AssetRouter.handlePayload`:
   - `$.usedPayloads[payload.id] = true` is set.
   - `IBaseLBTC(receipt.toToken).mint(receipt.recipient, receipt.amount)` completes.
   - 0 fee is transferred to `treasury`.
6. Claimer's `mintWithFee` transaction is mined and reverts with `AssetRouter_PayloadAlreadyUsed()`.
7. **Result:** Full loss of fee revenue and wasted claimer gas.

### PoC 2: Strategy NAV Update Revert
1. Strategy has `oldPps = 1e18`, `navAtSnapshot = 800_000e18`, `effectiveSupplyAtSnapshot = 1_000_000e18`.
2. Operator calls `fulfillRedeemRequests` for 900,000 shares before `postPricePerShare` is mined.
3. `effectiveSupplyNow = 100,000e18`.
4. `removalValue = (1_000_000 - 100_000) * 1e18 = 900_000e18`.
5. `scaled = navAtSnapshot * 1e18 = 800_000e18`.
6. `scaled < removalValue` (800k < 900k) evaluates to true.
7. Call reverts with `Strategy_InsufficientNavForReconciliation`.

---

## 3. Remediation
1. In `AssetRouter.sol`, add `onlyRole(CLAIMER_ROLE)` or restrict `mint` so that it can only be called by authenticated contracts (`StakedLBTC`, `StakeAndBake`).
2. In `StrategyBaseUpgradeable.postPricePerShare`, handle cases where `scaled < removalValue` gracefully by falling back to immediate asset-to-supply ratio rather than reverting, or lock redemption fulfillment during snapshot settlement windows.

---

## 4. Designated Researcher Payout Address
- **EVM Wallet:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Asset Preference:** USDC / USDT (ERC-20)
