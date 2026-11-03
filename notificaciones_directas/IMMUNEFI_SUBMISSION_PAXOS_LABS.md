# Immunefi Bug Report: Head-of-Line Blocking Denial of Service in Paxos BoringVault Withdrawal Queue

## Bug Description

### Target Program
- **Project:** Paxos Labs (`paxos-labs`)
- **Program Link:** https://immunefi.com/bug-bounty/paxos-labs/
- **In-Scope Assets:**
  - `src/base/Roles/WithdrawQueue.sol` (`0x69e0BF658bE5600864A946b4e5B911736D248FB4`)
  - `src/helper/one-to-one-queue/OneToOneQueue.sol`
  - `src/helper/PaxgyDynamicWithdrawalFeeModule.sol` (`0xF41e79D6e646f334C2fc4ea5Ae609707AE82264D`)
- **Impact Category:** Smart Contract -> Temporary/Permanent freezing of funds
- **Severity Level:** High Severity

---

## Vulnerability Details

### Root Cause & Vulnerability Mechanics
In `WithdrawQueue.sol`, user withdrawal orders are queued sequentially in a FIFO queue. Solvers execute `processOrders(ordersToProcess)` to fulfill orders starting from `lastProcessedOrder + 1`:

```solidity
uint256 vaultBalanceOfWantAsset = order.wantAsset.balanceOf(address(vault));
if (vaultBalanceOfWantAsset < expectedAssetsOut) {
    revert VaultInsufficientBalance(order.wantAsset, expectedAssetsOut, vaultBalanceOfWantAsset);
}
```

And similarly in `OneToOneQueue.sol`:
```solidity
function _checkBalanceQueue(IERC20 asset, uint256 amount, uint256 orderIndex) internal view {
    uint256 balance = asset.balanceOf(address(this));
    if (balance < amount) {
        revert InsufficientBalanceInQueue(orderIndex, address(asset), amount, balance);
    }
}
```

Whenever any single user order requires an amount greater than the vault's current liquid balance:
1. `processOrders` immediately reverts with `VaultInsufficientBalance` or `InsufficientBalanceInQueue`.
2. Because order processing is strictly sequential, the queue cannot skip the underfunded order.
3. The queue cursor (`lastProcessedOrder`) cannot advance past the blocked order.
4. All subsequent withdrawal orders (e.g. hundreds of smaller orders with amounts that could easily be satisfied by the vault's available liquidity) are completely blocked from being processed.
5. Users cannot force-process or bypass the blocked order because `forceProcessOrders` is restricted by `requiresAuth` to admin roles.

### Second Compounding Defect: Oracle Staleness Revert During Market Closures
In `WithdrawQueue.processOrders`:
```solidity
uint256 feeAmount = feeModule.calculateOfferFees(order.amountOffer, offerAsset, order.wantAsset, receiver);
```
`feeModule.calculateOfferFees` calls `PaxgXauRateProvider.getRate()`, which queries Chainlink's `XAU / USD` feed. Gold (XAU) is a traditional commodity with weekend market closures. When the feed does not update within `MAX_TIME_FROM_LAST_UPDATE`, `getRate()` reverts with `MaxTimeFromLastUpdatePassed`. Because `calculateOfferFees` is called without a `try/catch`, this halts `processOrders` completely during weekend or holiday market windows.
Furthermore, cancelled orders waiting for a refund are only refunded when `processOrders` reaches them, meaning user refunds are also frozen.

### Third Defect: `requiresAuth` on User Cancellation
`cancelOrder(uint256 orderIndex)` and `cancelOrderWithSignature` are decorated with `requiresAuth`. Despite the natspec explicitly specifying `@notice A user facing function for users to cancel their own orders`, the `requiresAuth` modifier rejects regular users who hold the order receipt NFT with `"UNAUTHORIZED"`, preventing users from cancelling their own queued orders.

---

## Proof of Concept (PoC)

1. Vault holds 200 PAXG in liquid balance.
2. User A queues order #10 requesting 500 PAXG.
3. Users B, C, D queue orders #11, #12, #13 requesting 10 PAXG each (total 30 PAXG).
4. Solver calls `processOrders(4)`.
5. When evaluating order #10, `vaultBalanceOfWantAsset (200) < expectedAssetsOut (500)`. Transaction reverts with `VaultInsufficientBalance`.
6. Result: Orders #11, #12, and #13 cannot be processed despite the vault having 200 PAXG available. The entire withdrawal queue remains completely frozen until 500 PAXG is deposited.

---

## Recommended Remediation

1. **Implement Queue Skipping / Deferred Orders:** In `processOrders`, if `vaultBalanceOfWantAsset < expectedAssetsOut`, skip the order and allow processing of subsequent orders that have sufficient liquidity, rather than reverting the entire batch.
2. **Remove `requiresAuth` from `cancelOrder`:** Remove `requiresAuth` from `cancelOrder` and `cancelOrderWithSignature` as authorization is already enforced via `ownerOf(orderIndex) == msg.sender` and signature verification.
3. **Decouple Refunds from Queue Cursor:** Allow immediate processing of refunds for cancelled orders rather than requiring the queue cursor to advance sequentially.

---

## Payout Destination
All bounties awarded for this disclosure must be sent to the researcher's EVM wallet:
`0x426d13134ee02f209bff6949cd2d2f209d57c964`
*(Networks: Arbitrum, Optimism, Ethereum Mainnet, Base, Sonic, Polygon)*
