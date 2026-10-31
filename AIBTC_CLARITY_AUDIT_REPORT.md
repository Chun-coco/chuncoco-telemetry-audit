# Security Audit: Jing BTC-In Contracts (Clarity Mainnet)
**Auditor:** @chuncoco / Antigravity Quant & Security Desk  
**Target Contracts:**
- `SPV9K21TBFAK4KNRJXF5DFP8N7W46G4V9RCJDC22.jing-btc-in-adapter` (279 lines)
- `SPV9K21TBFAK4KNRJXF5DFP8N7W46G4V9RCJDC22.jing-btc-in-escrow` (354 lines)
- `SPV9K21TBFAK4KNRJXF5DFP8N7W46G4V9RCJDC22.smart-buy-sbtc-trait` (24 lines)
**Commit Reference:** `Rapha-btc/jing-contracts-v3@6adced2`

---

## Executive Summary
We performed a static and invariant audit on the deployed Clarity bytecode of the Jing BTC-In infrastructure. The design employs a defensive balance-delta architecture (`held-before` vs `held-after`) to ensure escrow orders do not bleed collateral. However, our review isolated three key operational and economic vectors:

### Finding 1 [Medium/Low] - Escrow Execution Lacks Expiration Deadline Check
- **Contract:** `jing-btc-in-escrow.clar` (Function: `execute`, lines 58-150)
- **Vulnerability Detail:** The `order` record stores `cancel-height` (`stacks-block-height + cancel-after-blocks`). While `cancel` enforces `(asserts! (>= stacks-block-height (get cancel-height order)) ERR_TOO_EARLY)`, the `execute` function called by keepers **never reads or validates `cancel-height`**.
- **Impact:** If market conditions deteriorate and an order exceeds its desired execution window, a keeper can still execute the swap at stale market prices before the user's `cancel` transaction is mined.
- **Remediation:** Add `(asserts! (< stacks-block-height (get cancel-height order)) ERR_ORDER_EXPIRED)` at the start of `execute`.

### Finding 2 [Low] - Allowance Over-Allocation vs Collateral Contagion
- **Contract:** `jing-btc-in-escrow.clar` (Function: `execute`, line 80)
- **Vulnerability Detail:** Allowance is set to `(* u2 net)`. While line 105 asserts `(asserts! (<= spent net) ERR_OVERSPENT)`, if a router attempts to spend `> net` (e.g. 1.5x `net`), the transaction reverts via `ERR_OVERSPENT`. This protects user funds from theft, but causes a Denial of Execution (DoS) on legitimate fills where router rebating fails.

### Finding 3 [Low/Informational] - Event Log Misleading Indexers on Failed Router Swaps
- **Contract:** `jing-btc-in-escrow.clar` (Function: `execute`, lines 125-145)
- **Vulnerability Detail:** When a router returns an error code (`filled = false`), the contract emits `event: "btc-in-executed"` with `ok: false`, `spent: 0`, and `refund: net`. Off-chain indexers monitoring `btc-in-executed` without inspecting `ok` will incorrectly treat the transaction as a successful trade instead of a cancellation/refund.
- **Remediation:** Emit a dedicated `btc-in-execution-failed` event when `filled` is false.
