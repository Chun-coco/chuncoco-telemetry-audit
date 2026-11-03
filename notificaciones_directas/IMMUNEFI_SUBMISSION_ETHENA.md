# BUG BOUNTY DISCLOSURE: ETHENA LABS (USDE & SUSDE)
**Program:** Ethena Bug Bounty Program (Immunefi)  
**Program URL:** `https://immunefi.com/bug-bounty/ethena/`  
**Max Bounty Pool:** $3,000,000 USDC  
**Report Date:** November 03, 2026  
**Auditor / Submitter:** Chuncoco Telemetry & Security Engine  
**Designated Bounty Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964` (EVM Multichain)  

---

## 1. TARGET ASSET & REPOSITORY DETAILS
- **Project Name:** Ethena Labs
- **Repository:** `https://github.com/ethena-labs/bbp-public-assets`
- **Scope / Package:** `contracts/contracts/`
- **Impacted Contracts:**
  - `EthenaMinting.sol`
  - `StakedUSDeV2.sol`
  - `StakedUSDe.sol`

---

## 2. VULNERABILITY SUMMARY

### Vulnerability 1: Upper 192-bit Nonce Truncation Collision in `EthenaMinting.verifyNonce`
- **Severity:** High
- **Vulnerability Type:** Cryptographic / Logic Error (Order Invalidation Collision)
- **Location:** `contracts/contracts/EthenaMinting.sol#L443-L451`
- **Summary:**
  `verifyNonce` casts `uint256 nonce` into `uint64(nonce) >> 8`. Nonce values with differences in upper bits 64..255 share identical bitmap slots and bits. Executing an order with a lower nonce falsely invalidates legitimate subsequent orders differing only in higher-order bits, breaking market-maker arbitrage flows.

### Vulnerability 2: Cooldown Duration Reset Griefing in `StakedUSDeV2`
- **Severity:** Medium-High
- **Vulnerability Type:** Permanent / Extended Fund Freezing
- **Location:** `contracts/contracts/StakedUSDeV2.sol#L96-L118`
- **Summary:**
  Submitting secondary `cooldownAssets` or `cooldownShares` requests unconditionally overwrites `cooldowns[msg.sender].cooldownEnd = block.timestamp + cooldownDuration`. A staker with a large pending withdrawal near maturity gets their entire capital locked for another full 90-day cooldown period if a micro-withdrawal is executed.

### Vulnerability 3: Arithmetic Underflow Denial of Service in `StakedUSDe.totalAssets()`
- **Severity:** Medium
- **Vulnerability Type:** Denial of Service / Arithmetic Underflow Panic
- **Location:** `contracts/contracts/StakedUSDe.sol#L161-L163`
- **Summary:**
  `totalAssets()` calculates `balanceOf - getUnvestedAmount()`. If `getUnvestedAmount() > balanceOf`, Solidity 0.8.20 triggers an unchecked Panic(0x11), bricking all ERC-4626 core methods (deposits, redeems, mints, and withdraws).

---

## 3. PROPOSED REMEDIATIONS
1. **Fix Nonce Bitshifts:** In `verifyNonce`, use `nonce >> 8` and `1 << (nonce & 0xff)` without truncating to `uint64`.
2. **Independent Cooldown Queues:** Allow multiple cooldown tranches or average cooldown durations rather than overwriting the entire balance timer.
3. **Safe Total Assets Math:** Clamp `totalAssets()`: `return balance > unvested ? balance - unvested : 0;`.

---

## 4. FORMAL PAYOUT DESIGNATION
- **EVM Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
- **Preferred Token:** USDC
