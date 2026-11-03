# BUG BOUNTY DISCLOSURE: STARGATE PROTOCOL V2
**Program:** Stargate Protocol Bug Bounty Program (Immunefi)  
**Program URL:** `https://immunefi.com/bug-bounty/stargate/`  
**Max Bounty Pool:** $3,500,000 USD (USDT / USDC)  
**Report Date:** November 03, 2026  
**Auditor / Submitter:** Chuncoco Telemetry & Security Engine  
**Designated Bounty Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  

---

## 1. TARGET ASSET & REPOSITORY DETAILS
- **Project Name:** Stargate Protocol
- **Repository:** `https://github.com/stargate-protocol/stargate-v2`
- **Scope / Package:** `packages/stg-evm-v2/src`
- **Impacted Contracts:**
  - `peripheral/Planner.sol`
  - `feelibs/FeeLibV1.sol`
  - `peripheral/rewarder/StargateMultiRewarder.sol` & `StargateStaking.sol`
  - `StargatePoolNative.sol`
  - `peripheral/oft-wrapper/OFTWrapper.sol`

---

## 2. VULNERABILITY SUMMARY

### Vulnerability 1: Critical Boolean Logic Inversion in `Planner.multicall`
- **Severity:** High
- **Vulnerability Type:** Logic Error / Control Flow Bypass
- **Location:** `packages/stg-evm-v2/src/peripheral/Planner.sol#L34`
- **Summary:**
  `Planner.sol` defines a struct `Call` with field `bool allowFailure` ("whether to continue with the remaining calls in case of failure"). The Natspec specification states:
  > `@dev Reverts with CallFailed if a call fails and it has allowFailure = false.`
  
  In the implementation:
  ```solidity
  (bool success, bytes memory data) = call.target.call{ value: call.value }(call.data);
  if (call.allowFailure && !success) revert CallFailed(i, data);
  ```
  The condition evaluates to `true` when `allowFailure == true` and `!success`, causing an unintended transaction revert for tolerant calls, while silently swallowing failures when `allowFailure == false` (where execution is strictly expected to revert upon failure).

### Vulnerability 2: Arithmetic Underflow Panic (`0x11`) in `FeeLibV1._calculateFee`
- **Severity:** Medium-High
- **Vulnerability Type:** Arithmetic Underflow / Denial of Service
- **Location:** `packages/stg-evm-v2/src/feelibs/FeeLibV1.sol#L130-L142`
- **Summary:**
  `FeeLibV1.sol` permits fee configuration up to `FEE_DENOMINATOR` (100% fee). The internal calculation applies strict ceiling rounding:
  ```solidity
  fee = SafeCast.toUint64((uint256(_amountSD) * feeMill) / FEE_DENOMINATOR + 1);
  ```
  When `feeMill == FEE_DENOMINATOR`, `fee` computes to `_amountSD + 1`. In `applyFeeView`:
  ```solidity
  amountOutSD = amountInSD - _calculateFee(config, amountInSD);
  ```
  The subtraction underflows, triggering an uncaught Panic(0x11) in Solidity 0.8.22 and permanently bricking quote and transfer operations across that pathway.

### Vulnerability 3: Permanent LP Principal Freeze in `StargateStaking` via Coupled Reward Push
- **Severity:** High
- **Vulnerability Type:** Permanent Freezing of Unclaimed Yield / Principal Funds
- **Location:** `peripheral/rewarder/StargateMultiRewarder.sol#L40-L75`, `StargateStaking.sol#L59`
- **Summary:**
  `StargateStaking.withdraw()` directly invokes `self.rewarder.onUpdate(...)` which iterates through all registered reward tokens and triggers push transfers:
  ```solidity
  if (token == ETH) {
      (bool success, ) = to.call{ value: amount }("");
      if (!success) revert MultiRewarderNativeTransferFailed(token, amount);
  } else {
      IERC20(token).safeTransfer(to, amount);
  }
  ```
  If `user` is a smart contract unable to receive raw ETH or consuming higher gas, or if the reward pool is temporarily deficient in reward token liquidity, `onUpdate` reverts. Because reward distribution is coupled to the withdrawal of principal, stakers are completely locked out from redeeming their LP tokens.

---

## 3. PROPOSED REMEDIATIONS
1. **Fix `Planner.multicall`:** Update line 34 to `if (!call.allowFailure && !success) revert CallFailed(i, data);`.
2. **Cap Fee Calculation in `FeeLibV1`:** Ensure `fee = rawFee > _amountSD ? _amountSD : rawFee` to avoid underflow panics.
3. **Decouple Reward Distribution in Staking:** Adopt a pull-based reward claim mechanism or catch reward transfer failures so LP principal withdrawals are never obstructed.
4. **Resilience in Native Outflow:** Provide fallback wrapping to WETH or alternative receiver designation for cached native outflows.

---

## 4. FORMAL PAYOUT DESIGNATION
In accordance with Immunefi rules and responsible disclosure guidelines, please route all applicable bounty awards to:
- **EVM Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Preferred Token:** USDT / USDC
