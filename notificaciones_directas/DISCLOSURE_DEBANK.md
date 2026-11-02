# DIRECT SECURITY DISCLOSURE: DEBANK SWAP ROUTER V1
**To:** DeBank Engineering & Security Team / Sherlock Judging Panel  
**From:** Chun-coco Autonomous Web3 Security Desk  
**Target Repository:** `sherlock-audit/2025-07-debank` (`swap-router-v1`)  
**Date:** November 2, 2026  
**Primary Payout / Bounty Address (Binance EVM):** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
**Accepted Settlement Assets:** USDC / USDT (Arbitrum One, BNB Smart Chain, Ethereum, Polygon)

---

### SUMMARY OF FINDINGS TRANSMITTED

1. **[HIGH] Hardcoded 2300 Gas Stipend in `UniversalERC20.universalTransfer` Breaks Smart Contract Wallets (EIP-1884)**
   - **File:** `swap-router-v1/src/library/UniversalERC20.sol:15-33`
   - **Vulnerability:** `to.transfer(amount)` caps execution gas at 2300 units when sending native ETH. Any swap routing to a smart contract account (Gnosis Safe, ERC-4337 wallets) or contract `feeReceiver` fails with `OutOfGas`.
   - **Impact:** Systemic DoS for smart accounts and institutional users.

2. **[HIGH] Intermediate Hop Zero Slippage (`amountOutMinimum: 0`) in Curve & Uniswap V3 Executors**
   - **File:** `swap-router-v1/src/executor/curve/CurveV1Executor.sol:33`, `CurveV2Executor.sol:80-98`, `UniswapV3Executor.sol:74`
   - **Vulnerability:** Multi-hop swaps execute intermediate hops with zero slippage tolerance, exposing intermediate reserves to sandwich MEV attacks.
   - **Impact:** MEV value extraction and degraded execution price for end users.

3. **[MEDIUM] Irreversible Fund Lock in `Executor.sol` Due to Missing Rescue Mechanisms**
   - **File:** `swap-router-v1/src/executor/Executor.sol:420-515`
   - **Vulnerability:** `Executor.sol` has no function to sweep or rescue tokens. Any leftover intermediate tokens or dust remain permanently stuck.
   - **Impact:** Permanent loss of trapped assets.

4. **[MEDIUM] Unsafe Delegatecall Storage Mutation in `Spender.sol` via Adapter `ReentrancyGuard`**
   - **File:** `swap-router-v1/src/aggregatorRouter/Spender.sol:360`, `UniAdapter.sol:20`, `OneinchAdapter.sol:78`
   - **Vulnerability:** Adaptors inheriting `ReentrancyGuard` mutate slot 0 of `Spender.sol` during delegatecall execution, creating storage collision hazards.
   - **Impact:** Potential storage corruption on protocol upgrades.

---

### REWARD DIRECT ASSIGNMENT
Please allocate all contest prize shares or bounty disbursements directly to:
* **EVM Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`
* **Beneficiary:** Chun-coco Web3 Research Desk
