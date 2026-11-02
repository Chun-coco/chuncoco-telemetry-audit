# DIRECT VULNERABILITY DISCLOSURE & PAYOUT ROUTING

**Target Protocol:** Superfluid Locker System (FLUID / SUP Staking & Vesting Engine)  
**Contest Identifier:** `2025-06-superfluid-locker-system` (Sherlock Audits)  
**Total Reward Pool:** $30,000 USDC  
**Submission Auditor:** Chun-coco Security Research Group (`@chuncoco`)  
**Designated EVM Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
*(Supported networks: Arbitrum One, Optimism, Ethereum Mainnet, Polygon, BNB Chain)*  

---

## Findings Summary

1. **[CRITICAL] Cross-Chain Signature Replay Attack in `EPProgramManager.sol`:**
   - **File:** `fluid/packages/contracts/src/EPProgramManager.sol` (Line 274)
   - **Root Cause:** `_verifySignature` computes `keccak256(abi.encodePacked(user, newUnits, programId, nonce))` without `block.chainid` or `address(this)`.
   - **Impact:** Legitimate signatures on one network can be broadcast and replayed across all 11 deployed chains, multiplying claimant pool units and draining ecosystem token distribution pools.

2. **[HIGH] Premature Insolvency & Keeper Liquidation in `Fontaine.sol` due to Missing Superfluid Buffer Deposits:**
   - **File:** `fluid/packages/contracts/src/FluidLocker.sol` (Line 606) & `Fontaine.sol`
   - **Root Cause:** 3 simultaneous Superfluid flows lock up to 12 hours of buffer deposits. `FluidLocker` transfers only exact stream principal without the buffer, causing `Fontaine`'s streamable balance to exhaust before `endDate`.
   - **Impact:** Superfluid sentinel keeper bots liquidate the streams, slashing the buffer and stopping user unlocks prematurely.

3. **[HIGH] Involuntary Rewards Halting on Partial Unstake in `FluidLocker.unstake`:**
   - **File:** `fluid/packages/contracts/src/FluidLocker.sol` (Line 390)
   - **Root Cause:** Unconditionally calling `FLUID.disconnectPool(STAKER_DISTRIBUTION_POOL)` when `_stakedBalance > 0` disconnects stakers from GDA rewards for their remaining stake.

4. **[MEDIUM] Irretrievable SUP Token Lockout on Early Liquidity Exit:**
   - **File:** `fluid/packages/contracts/src/FluidLocker.sol` (Line 464)
   - **Root Cause:** Burning position NFTs and deleting exit timestamps leaves early-withdrawn SUP trapped in the locker contract bytecode.

5. **[MEDIUM] MEV Sandwich Vulnerability in `FluidLocker._pump` via Zero Minimum Output:**
   - **File:** `fluid/packages/contracts/src/FluidLocker.sol` (Line 635)
   - **Root Cause:** Hardcoding `amountOutMinimum: 0` in Uniswap V3 swap.

---

## Payout Destination
All bounty allocations, rewards, and judging disbursements for this submission MUST be credited directly to the official payout wallet:
`0x426d13134ee02f209bff6949cd2d2f209d57c964`
