# IMMUNEFI BUG BOUNTY DISCLOSURE: 1INCH LIMIT ORDER PROTOCOL
**Target:** 1inch - Smart Contracts (`1inch-SmartContracts`)  
**Program URL:** https://immunefi.com/bug-bounty/1inch-SmartContracts/  
**Repository:** https://github.com/1inch/limit-order-protocol (Commit: `50bd130`, v4.3.4)  
**Severity:** High  
**Vulnerability Type:** Network Incompatibility / Arithmetic Panic / Griefing DoS on Fee Delivery  
**Researcher Designated Payout Address (EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
(Networks: Arbitrum, Optimism, Ethereum Mainnet, Base, Sonic, Polygon)

---

## 1. Vulnerability Summary
Three technical vulnerabilities were identified in the 1inch Limit Order Protocol v4 contracts:

1. **Hardcoded Permit2 Address in `Permit2WitnessProxy.sol` Defeating zkSync Era Deployments:**
   `Permit2WitnessProxy.sol` hardcodes the constant address `0x000000000022D473030F116dDEE9F6B43aC78BA3`. On networks like zkSync Era (where Uniswap Permit2 is deployed at `0x0000000000225e31d15943971f47ad3022f714fa`), all orders utilizing Permit2 Witness signing fail because the target contract has no deployed bytecode, completely bricking witness-based limit orders on that chain.

2. **Underflow and Division by Zero Panics in `DutchAuctionCalculator.sol`:**
   In `_calculateAuctionTakingAmount`, `(endTime - startTime)` underflows with `Panic(0x11)` or divides by zero with `Panic(0x12)` if `endTime <= startTime`. Additionally, if `takingAmountEnd == 0`, `calculatedTakingAmount` reaches 0, reverting `getMakingAmount` calls.

3. **Griefing Denial of Service on Integrator Fee Reversion in `FeeTaker._sendEth`:**
   `FeeTaker._sendEth` forces strict reverts on failed native ETH transfers to `integratorFeeRecipient`. A misconfigured or rejecting fee contract bricks the entire order fill for all takers.

---

## 2. Proof of Concept (PoC)

### PoC: Incompatible Permit2 on zkSync Era
1. A limit order is deployed on zkSync Era with `makerTraits.usePermit2()` and witness data.
2. The settlement contract routes through `Permit2WitnessProxy.func_801zDya`.
3. `Permit2WitnessProxy` invokes `_PERMIT2.permitWitnessTransferFrom` at `0x000000000022D473030F116dDEE9F6B43aC78BA3`.
4. On zkSync Era, no contract exists at `0x000000000022D473030F116dDEE9F6B43aC78BA3`.
5. The call fails, aborting the order fill transaction.

---

## 3. Remediation
1. In `Permit2WitnessProxy.sol`, pass `_permit2` as an immutable constructor parameter (as done in `Permit2Proxy.sol`).
2. In `DutchAuctionCalculator.sol`, enforce `require(endTime > startTime)` and bound `calculatedTakingAmount` to a minimum of 1 wei.
3. In `FeeTaker.sol`, handle fee transfer failures gracefully or convert to WETH fallback.

---

## 4. Designated Researcher Payout Address
- **EVM Wallet:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Asset Preference:** USDC (ERC-20)
