# DIRECT VULNERABILITY DISCLOSURE & PAYOUT ROUTING

**Target Protocol:** Yearn Finance yBOLD (`yv3-liquityv2-sp-strategy`)  
**Contest Identifier:** `2025-05-yearn-ybold` (Sherlock Audits)  
**Total Reward Pool:** $14,500 USDC  
**Submission Auditor:** Chun-coco Security Research Group (`@chuncoco`)  
**Designated EVM Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
*(Supported networks: Arbitrum One, Optimism, Ethereum Mainnet, Polygon, BNB Chain)*  

---

## Findings Summary

1. **[CRITICAL] Mathematical Flaw in `Accountant.report` Violates 1:1 Invariant & Dilutes Depositors on Loss Recovery:**
   - **Contract:** `src/periphery/Accountant.sol` (Lines 177-185)
   - **Root Cause:** In Yearn `VaultV3.vy._process_report`, `accountant.report` executes prior to updating debt with the newly reported `gain`. When recovering from a previous loss (`assets < supply`), `Accountant` charges `totalFees = gain - needed`. However, `VaultV3._convert_to_shares` converts these fee assets to shares using the unadjusted, discounted pre-gain price per share ($\text{PPS} < 1.0$).
   - **Impact:** The vault issues more shares than the surplus profit ($\text{shares} > \text{totalFees}$), mathematically forcing the post-report PPS to stay strictly below 1.0 ($\text{PPS} < 1.0$). Depositors permanently lose equity and the 1:1 invariant is permanently broken across consecutive loss-recovery cycles.

2. **[CRITICAL] Triple WAD Division in `Strategy._tend` Truncates Auction Starting Price by 10^18:**
   - **Contract:** `src/Strategy.sol` (Line 241)
   - **Root Cause:** Line 241 calculates `AUCTION.setStartingPrice(_available * _price / WAD * _bufferPercentage / WAD / WAD)`. Dividing by `WAD` three times reduces an 18-decimal token valuation into an integer.
   - **Impact:** Any collateral balance valued under $1.00 USD (e.g. 0.0003 ETH) evaluates to zero starting price, causing either an immediate revert on `setStartingPrice(0)` (freezing the strategy from ever auctioning collateral) or allowing MEV bots to purchase the entire collateral lot for 0 BOLD.

3. **[HIGH] Staker Strategy Harvest DoS Due to Modifier Restriction in `Accountant.distribute`:**
   - **Contracts:** `src/Staker.sol` (Line 49) & `src/periphery/Accountant.sol` (Lines 377-386)
   - **Root Cause:** `LV2SPStakerStrategy._harvestAndReport()` calls `ACCOUNTANT.distribute(address(asset))`, which forwards to `distribute(token, amount)` gated by `onlyFeeManagerOrRecipient`. Because `Accountant` is deployed before `LV2SPStakerStrategy`, the `feeRecipient` is not initialized to the strategy.
   - **Impact:** Any attempt by keepers to harvest `st-yBOLD` reverts with `"!recipient"`, halting all yield distributions to staked depositors.

4. **[HIGH] Unbounded Iteration Over Troves in `StrategyAprOracle.aprAfterDebtChange` Bricks Rebalancing:**
   - **Contract:** `src/periphery/StrategyAprOracle.sol` (Lines 92-105)
   - **Root Cause:** Iterates through every single trove in the Liquity V2 market via `getMultipleSortedTroves(..., 0, _count)`.
   - **Impact:** Exceeds the 30M EVM block gas limit in active markets with thousands of troves, causing Out-of-Gas reverts on automated Yearn V3 debt reallocation transactions.

5. **[MEDIUM] Divide-Before-Multiply Precision Collapse in `StrategyAprOracle`:**
   - **Contract:** `src/periphery/StrategyAprOracle.sol` (Line 111)
   - **Root Cause:** Integer division `_weightedInterestRate / _totalDebt` executed before multiplication truncates small interest rate basis points to zero.

---

## Payout Destination
All bounty allocations, rewards, and judging disbursements for this submission MUST be credited directly to the official payout wallet:
`0x426d13134ee02f209bff6949cd2d2f209d57c964`
