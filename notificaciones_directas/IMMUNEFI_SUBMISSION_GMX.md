# BUG BOUNTY DISCLOSURE: GMX V2 (SYNTHETICS)
**Program:** GMX Bug Bounty Program (Immunefi)  
**Program URL:** `https://immunefi.com/bug-bounty/gmx/`  
**Max Bounty Pool:** $5,000,000 USD (ETH / USDC)  
**Report Date:** November 03, 2026  
**Auditor / Submitter:** Chuncoco Telemetry & Security Engine  
**Designated Bounty Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  

---

## 1. TARGET ASSET & REPOSITORY DETAILS
- **Project Name:** GMX
- **Repository:** `https://github.com/gmx-io/gmx-synthetics`
- **Scope / Module:** `contracts/order/OrderUtils.sol` & `contracts/market/MarketUtils.sol`
- **Impacted Contracts:**
  - `OrderUtils.sol`
  - `OrderVault.sol`

---

## 2. VULNERABILITY SUMMARY

### Vulnerability 1: Execution Fee Siphoning via Excess Balance Overwrite in `OrderUtils.createOrder`
- **Severity:** High
- **Vulnerability Type:** Logic Error / Fee Siphoning
- **Location:** `contracts/order/OrderUtils.sol#L119-L126`
- **Summary:**
  `createOrder` assigns `params.numbers.executionFee = wntAmount`, where `wntAmount` is measured via `orderVault.recordTransferIn(cache.wnt)`. When extraneous WNT or dust is deposited, the execution fee is automatically inflated to match the entire recorded balance change. When the keeper completes the order, the full inflated execution fee is transferred to the keeper, enabling unintended siphoning of vault balances.

---

## 3. PROPOSED REMEDIATIONS
1. **Fix Fee Attribution:** Enforce `order.setExecutionFee(params.numbers.executionFee)` and safely refund any delta `wntAmount - executionFee` back to the account.

---

## 4. FORMAL PAYOUT DESIGNATION
- **EVM Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Preferred Token:** ETH or USDC
