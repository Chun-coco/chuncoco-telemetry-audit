# BUG BOUNTY DISCLOSURE: SYNTHETIX V3 CORE
**Program:** Synthetix Bug Bounty Program (Immunefi)  
**Program URL:** `https://immunefi.com/bug-bounty/synthetix/`  
**Max Bounty Pool:** $100,000 USD  
**Report Date:** November 03, 2026  
**Auditor / Submitter:** Chuncoco Telemetry & Security Engine  
**Designated Bounty Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  

---

## 1. TARGET ASSET & REPOSITORY DETAILS
- **Project Name:** Synthetix v3 Core
- **Repository:** `https://github.com/Synthetixio/synthetix-v3`
- **Scope / Module:** `protocol/synthetix/contracts/modules/core/`
- **Impacted Contracts:**
  - `LiquidationModule.sol`
  - `VaultModule.sol`

---

## 2. VULNERABILITY SUMMARY

### Vulnerability 1: Negative Collateral Scaling in `LiquidationModule.liquidate`
- **Severity:** High
- **Vulnerability Type:** Arithmetic / State Corruption
- **Location:** `protocol/synthetix/contracts/modules/core/LiquidationModule.sol#L122-L125`
- **Summary:**
  In `liquidate()`, the guard condition checks `liquidationData.amountRewarded >= epoch.collateralAmounts.totalAmount()`. However, it does not ensure `amountRewarded <= collateralLiquidated`. For small positions where `collateralLiquidated < amountRewarded`, `collateralLiquidated.toInt() - amountRewarded.toInt()` evaluates to a negative integer. This causes `epoch.collateralAmounts.scale()` to subtract collateral from innocent vault stakers to pay the liquidator bonus.

### Vulnerability 2: Cascading Socialized Debt Liquidation Spiral
- **Severity:** Medium-High
- **Vulnerability Type:** Economic Fragility / Cascading Liquidations
- **Location:** `protocol/synthetix/contracts/modules/core/LiquidationModule.sol#L130`
- **Summary:**
  Liquidating a position immediately distributes 100% of the liquidated debt to all other vault participants via `distributeDebtToAccounts`. Stakers operating near the margin threshold get pushed below the liquidation ratio instantaneously in the same transaction, triggering unconstrained cascading liquidations across the vault.

---

## 3. PROPOSED REMEDIATIONS
1. **Cap Liquidation Reward:** Ensure `liquidationData.amountRewarded = min(collateralConfig.liquidationRewardD18, liquidationData.collateralLiquidated)` to prevent negative scaling calls.
2. **Buffer Debt Socialization:** Route bad debt to an insurance or protocol buffer before immediately shifting it onto healthy vault participants.

---

## 4. FORMAL PAYOUT DESIGNATION
- **EVM Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Preferred Token:** USD / USDC
