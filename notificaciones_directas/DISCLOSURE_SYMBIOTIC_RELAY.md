# DIRECT VULNERABILITY DISCLOSURE & PAYOUT ROUTING

**Target Protocol:** Symbiotic Relay (Middleware SDK)  
**Contest Identifier:** `2025-06-symbiotic-relay` (Sherlock Audits)  
**Total Reward Pool:** $67,500 USDC  
**Submission Auditor:** Chun-coco Security Research Group (`@chuncoco`)  
**Designated EVM Payout Address:** `0x426d13134ee02f209bff6949cd2d2f209d57c964`  
*(Supported networks: Arbitrum One, Optimism, Ethereum Mainnet, Polygon, BNB Chain)*  

---

## Findings Summary

1. **[CRITICAL] Insufficient `PAIRING_CHECK_GAS_LIMIT` Causes Permanent BLS BN254 Signature Verification Failure Under EIP-1108:**
   - **File:** `middleware-sdk/src/contracts/libraries/sigs/SigBlsBn254.sol` (Line 11) & `BN254.sol`
   - **Root Cause:** EIP-1108 specifies `34,000 + 45,000 * 2 = 124,000` gas for the 2-pair ECPAIRING precompile (0x08). The contract hardcodes `PAIRING_CHECK_GAS_LIMIT = 120_000`. The staticcall always runs out of gas, causing all BLS BN254 signature and quorum verifications to fail on EVM networks.
   - **Impact:** Total failure of the cryptographic verification layer and consensus settlement.

2. **[HIGH] Arithmetic Underflow and Division by Zero in `EpochManager.getEpochIndex`:**
   - **File:** `middleware-sdk/src/contracts/modules/valset-driver/EpochManager.sol` (Line 89)
   - **Root Cause:** Calling `getEpochIndex` with `timestamp < epochDurationTimestamp` triggers an arithmetic underflow (`Panic(0x11)`), and uninitialized lookup triggers division by zero (`Panic(0x12)`).

3. **[HIGH] Quorum Threshold Bypass via Unchecked Arithmetic Underflow:**
   - **File:** `middleware-sdk/src/contracts/modules/settlement/sig-verifiers/SigVerifierBlsBn254Simple.sol` (Line 144)
   - **Root Cause:** `unchecked` subtraction `totalVotingPower - nonSignersVotingPower` wraps to $2^{256} - 1$ if `nonSignersVotingPower > totalVotingPower`, bypassing the quorum threshold check.

4. **[MEDIUM] `console2.logBytes` Left in Production Bytecode:**
   - **File:** `middleware-sdk/src/contracts/modules/settlement/sig-verifiers/SigVerifierBlsBn254Simple.sol` (Line 52)

5. **[MEDIUM] Missing `safeTransferFrom` in `BaseRewardsLogic.distributeStakerRewards`:**
   - **File:** `middleware-sdk/src/contracts/modules/voting-power/extensions/logic/BaseRewardsLogic.sol`

---

## Payout Destination
All bounty allocations, rewards, and judging disbursements for this submission MUST be credited directly to the official payout wallet:
`0x426d13134ee02f209bff6949cd2d2f209d57c964`
