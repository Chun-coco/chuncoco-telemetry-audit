# IMMUNEFI BUG BOUNTY DISCLOSURE: COW PROTOCOL
**Target:** CoW Protocol (`cowprotocol`)  
**Program URL:** https://immunefi.com/bug-bounty/cowprotocol/  
**Repository:** https://github.com/cowprotocol/contracts (Commit: `c07a93e`)  
**Severity:** High  
**Vulnerability Type:** Denial of Service / Arithmetic Overflow / Fund Invariant Degradation  
**Researcher Designated Payout Address (EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
(Networks: Arbitrum, Optimism, Ethereum Mainnet, Base, Sonic, Polygon)

---

## 1. Vulnerability Summary
Two primary technical flaws exist in the core settlement engine of CoW Protocol (GPv2):

1. **Denial of Service in Batch Settlements via Fixed 2300-Gas Native ETH Transfers:**
   In `GPv2Transfer.sol`, native ETH payouts to order recipients are executed via `payable(transfer.account).transfer(transfer.amount)`. Because `.transfer()` forwards a strict 2,300 gas stipend, any order where the recipient is a Smart Contract Wallet (e.g. Gnosis Safe, Argent, ERC-4337 smart account) or executes standard event logging in its `receive()` handler will revert with Out of Gas. Because this call occurs inside the batch `settle` loop, the single failing transfer reverts the entire multi-trade settlement batch, wasting solver gas and preventing execution.

2. **Multiplication Overflow in Limit Price Calculation (`SafeMath.mul`):**
   In `GPv2Settlement.computeTradeExecution`, `order.sellAmount.mul(sellPrice) >= order.buyAmount.mul(buyPrice)` is checked using 256-bit SafeMath multiplication. For high-supply tokens or meme tokens with large balances, `sellAmount * sellPrice` exceeds `2^256 - 1`, reverting valid settlement transactions.

---

## 2. Proof of Concept (PoC)

### PoC: DoS on Smart Contract Recipient of Native ETH
1. A user places a valid buy order for ETH through a Gnosis Safe or contract wallet.
2. The user's contract implements:
   ```solidity
   receive() external payable {
       emit EthReceived(msg.sender, msg.value); // costs ~2,800+ gas
   }
   ```
3. A solver matches the order into a batch with 10 other trades and calls `GPv2Settlement.settle(...)`.
4. In `vault.transferToAccounts(outTransfers)`:
   - `GPv2Transfer.transferToAccounts` reaches the user's order:
   - `payable(transfer.account).transfer(transfer.amount)` is invoked with 2,300 gas.
   - The recipient's `receive()` function runs out of gas.
   - The subcall reverts with `EvmError: OutOfGas`.
5. The entire `settle` transaction reverts. All 10 trades fail to settle, and the solver forfeits transaction execution costs.

---

## 3. Remediation
1. Replace `.transfer()` in `GPv2Transfer.sol` with:
   ```solidity
   (bool success, ) = payable(transfer.account).call{value: transfer.amount}("");
   require(success, "GPv2: ETH transfer failed");
   ```
2. Utilize full 512-bit intermediate math (e.g. `FullMath.mulDiv`) when validating limit prices for high-supply assets.

---

## 4. Designated Researcher Payout Address
- **EVM Wallet:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Asset Preference:** USDC (ERC-20)
