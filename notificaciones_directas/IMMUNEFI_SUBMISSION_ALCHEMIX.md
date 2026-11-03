# IMMUNEFI BUG BOUNTY DISCLOSURE: ALCHEMIX V3
**Target:** Alchemix (`alchemix-1`)  
**Program URL:** https://immunefi.com/bug-bounty/alchemix-1/  
**Repository:** https://github.com/alchemix-finance/v3 (Commit: `d78738d`)  
**Severity:** High  
**Vulnerability Type:** Economic Logic Defect / Bad Debt Accumulation / DoS on Deposits  
**Researcher Designated Payout Address (EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
(Networks: Arbitrum, Optimism, Ethereum Mainnet, Base, Sonic, Polygon)

---

## 1. Vulnerability Summary
Two critical security defects were identified in the Alchemix v3 protocol contracts:

1. **Collateral Drain via Fee Clamping with Zero Debt Burn in `AlchemistV3._doLiquidation`:**
   In `AlchemistV3._doLiquidation`, liquidator fee calculations derive from idealized surplus math (`baseFee`), but the realized fee clamps to `amountLiquidated` when collateral is degraded. When `requestedFeeInYield >= amountLiquidated`, the liquidator receives 100% of the account's remaining collateral as a fee, leaving `netToTransmuter = 0` and `debtToBurn = 0`. The entire unbacked synthetic debt remains in the system with 0 collateral backing.

2. **Permanent Denial of Service on Protocol Deposits During Undercollateralization (`AlchemistV3.deposit`):**
   `AlchemistV3.deposit` strictly enforces `!_isProtocolInBadDebt()`. If the protocol experiences bad debt (`totalSyntheticsIssued > backingDebt`), all deposit attempts globally revert with `InvalidState()`. The vault cannot accept new collateral to recapitalize itself, creating an irreversible death spiral.

---

## 2. Technical Analysis & Scenario Walkthrough

### Scenario 1: Collateral Drain Without Debt Burn
1. Account #42 has debt = 10,000 alUSD and collateral = 8,500 USD equivalent in yield tokens (unhealthy position).
2. A liquidator triggers `AlchemistV3.liquidate(42)`.
3. In `_doLiquidation`:
   - `liquidationAmount` requests the position's collateral.
   - `amountLiquidated = _subCollateralBalance(...)` returns 8,500.
   - Idealized calculation yields `requestedFeeInYield = 8,500` (or higher due to baseFee calculations).
   - `feeInYield = requestedFeeInYield > amountLiquidated ? amountLiquidated : requestedFeeInYield` => `feeInYield = 8,500`.
   - `netToTransmuter = amountLiquidated - feeInYield = 8,500 - 8,500 = 0`.
   - `maxDebtByRealized = convertYieldTokensToDebt(0) = 0`.
   - `debtToBurn` is capped to 0.
4. **Outcome:** Liquidator receives 8,500 yield tokens. 0 alUSD debt is burned. The system's total debt is unreduced, creating 10,000 alUSD of pure unbacked synthetic debt.

### Scenario 2: Protocol Deposit Freeze
1. Bad debt is created through insolvency or bad liquidations, causing `_isProtocolInBadDebt()` to return `true`.
2. Any depositor attempting `alchemist.deposit(amount, recipient, tokenId)` reverts on `_checkState(!_isProtocolInBadDebt())`.
3. Protocol cannot be recapitalized through collateral deposits.

---

## 3. Remediation
1. In `AlchemistV3._doLiquidation`, ensure liquidator fee is strictly calculated as a percentage of `amountLiquidated` (`feeInYield = amountLiquidated * feeBps / BPS`), guaranteeing that a positive fraction of seized collateral always cancels synthetic debt.
2. Remove `_checkState(!_isProtocolInBadDebt())` from `deposit` to allow collateral inflows to restore solvency.

---

## 4. Designated Researcher Payout Address
- **EVM Wallet:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Asset Preference:** USDC (ERC-20)
