# Chun-coco Cryptographic Telemetry & Audit Node

Public, unauthenticated, git-backed telemetry feed for `@chuncoco` (Antigravity Quant Desk on AWS EC2 `13.53.36.244`).

## Grade B / A Auditor Verification Specification
This repository maintains an immutable cryptographic commit ledger generated every 60 minutes via crontab. It directly reconciles exchange-signed Binance Futures income and trade events.

### Ledger Contents
- `balance_anchor.json`: Exact real-time snapshot of USDT collateral directly from Binance Futures account API.
- `income_ledger.json`: Raw record of the last 100 realized PnL events, taker/maker trading commissions, and funding fees.
- `user_trades.json`: Microstructure execution records across all 16 dynamically scanned perp contracts (entry/exit fills, order IDs, timestamps).
- `manifest_sha256.json`: Root Merkle-tree hash of all files at each hourly snapshot, signed under Git commit SHA.

### Cryptographic Verification
To independently verify the ledger:
```bash
# Check root hash integrity
sha256sum balance_anchor.json income_ledger.json user_trades.json
# Compare with manifest_sha256.json
cat manifest_sha256.json
```

### Risk Invariants & Sniper Gates
- Maximum daily trades: 12 (Axel) / 10 (Don Luis)
- Loss freeze cooldown: 3600s (60 min)
- Max allowed bid-ask spread: 7.0 bps (0.07%)
- Partial exits: GTX Maker-only at 1.55R (+0.775%)

