#!/usr/bin/env python3
"""
Chun-coco Public Audit Feeds & Secured Dashboard (Grade B/A)
Public read-only endpoints for @eveescout and automated quant crawlers.
"""
import os
import sys
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from http import cookies

REPO_DIR = '/home/ubuntu/chuncoco_telemetry_audit'
PORT = 8787

VALID_TOKENS = {
    "eveescout_audit_key_9f69": "EVEEscout Primary Verifier",
    "chuncoco_guest_alpha_2026": "Invited Quant Peer",
    "axel_master_admin_v10": "Principal Admin"
}

def check_auth(headers, query_params):
    token = query_params.get("token", [None])[0] or query_params.get("key", [None])[0]
    if token and token in VALID_TOKENS:
        return token, VALID_TOKENS[token]

    h_token = headers.get("X-Audit-Token")
    if h_token and h_token in VALID_TOKENS:
        return h_token, VALID_TOKENS[h_token]

    auth_header = headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        b_token = auth_header[7:].strip()
        if b_token in VALID_TOKENS:
            return b_token, VALID_TOKENS[b_token]

    cookie_str = headers.get("Cookie", "")
    if cookie_str:
        c = cookies.SimpleCookie()
        try:
            c.load(cookie_str)
            if "audit_token" in c:
                c_val = c["audit_token"].value
                if c_val in VALID_TOKENS:
                    return c_val, VALID_TOKENS[c_val]
        except Exception:
            pass

    return None, None

def get_html_dashboard(token="public_guest", role="Public Quant Auditor"):
    manifest = {}
    try:
        with open(os.path.join(REPO_DIR, 'manifest_sha256.json'), 'r') as f:
            manifest = json.load(f)
    except Exception:
        pass

    summary = manifest.get("reconciliation_summary", {})
    balance = manifest.get("usdt_balance_anchor", {}).get("balance", "N/A")
    commit_sha = manifest.get("git_commit_sha", "HEAD")[:10]
    root_sha = manifest.get("manifest_root_sha256", "N/A")
    gen_time = manifest.get("generated_at_utc", "N/A")

    bot_alpha = summary.get("BOT_ALPHA", {})
    manual_pnl = summary.get("MANUAL_ADOPTED", {}).get("net_pnl", 0.0)
    transfer_amt = summary.get("CAPITAL_TRANSFER", {}).get("total_transfer", 0.0)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chun-coco Quant Telemetry // Grade B/A Audit Portal</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;600;700;800&family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #090d16;
  --panel: #111827;
  --panel-border: #1f293d;
  --accent: #00f2fe;
  --accent-glow: rgba(0, 242, 254, 0.25);
  --green: #10b981;
  --green-glow: rgba(16, 185, 129, 0.2);
  --red: #ef4444;
  --text: #f3f4f6;
  --text-muted: #9ca3af;
  --gold: #f59e0b;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: 'Inter', sans-serif;
  min-height: 100vh;
  padding: 24px;
}}
.container {{
  max-width: 1280px;
  margin: 0 auto;
}}
header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--panel-border);
  margin-bottom: 24px;
}}
.logo-title h1 {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 24px;
  font-weight: 800;
  letter-spacing: -0.5px;
  background: linear-gradient(90deg, #00f2fe 0%, #4facfe 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: flex;
  align-items: center;
  gap: 10px;
}}
.badge-live {{
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid var(--green);
  color: var(--green);
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 700;
  padding: 4px 10px;
  border-radius: 9999px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}}
.badge-live::before {{
  content: "";
  width: 7px;
  height: 7px;
  background: var(--green);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--green);
  animation: pulse 1.5s infinite;
}}
@keyframes pulse {{
  0% {{ opacity: 0.4; transform: scale(0.9); }}
  50% {{ opacity: 1; transform: scale(1.1); }}
  100% {{ opacity: 0.4; transform: scale(0.9); }}
}}
.user-badge {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  background: #1e293b;
  border: 1px solid #334155;
  padding: 6px 14px;
  border-radius: 8px;
  color: var(--accent);
}}
.stats-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}}
.card {{
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 12px;
  padding: 20px;
  position: relative;
  overflow: hidden;
  transition: transform 0.2s, border-color 0.2s;
}}
.card:hover {{
  transform: translateY(-2px);
  border-color: rgba(0, 242, 254, 0.4);
}}
.card .label {{
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-muted);
  margin-bottom: 8px;
  font-family: 'JetBrains Mono', monospace;
}}
.card .value {{
  font-size: 26px;
  font-weight: 800;
  font-family: 'JetBrains Mono', monospace;
}}
.card .sub {{
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
}}
.text-green {{ color: var(--green); text-shadow: 0 0 10px var(--green-glow); }}
.text-cyan {{ color: var(--accent); text-shadow: 0 0 10px var(--accent-glow); }}
.text-gold {{ color: var(--gold); }}

.main-grid {{
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 24px;
}}
@media (max-width: 900px) {{
  .main-grid {{ grid-template-columns: 1fr; }}
}}
.section-title {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 16px;
  font-weight: 700;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--accent);
}}
.hash-box {{
  background: #0d131f;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  word-break: break-all;
  margin-bottom: 10px;
}}
.endpoints-list a {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #0d131f;
  border: 1px solid #1e293b;
  border-radius: 8px;
  padding: 12px 16px;
  margin-bottom: 10px;
  color: var(--text);
  text-decoration: none;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  transition: all 0.2s;
}}
.endpoints-list a:hover {{
  background: #172236;
  border-color: var(--accent);
  color: var(--accent);
  transform: translateX(4px);
}}
.copy-pill {{
  background: rgba(0, 242, 254, 0.1);
  color: var(--accent);
  border: 1px solid rgba(0, 242, 254, 0.3);
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 11px;
}}
.curl-box {{
  background: #05080f;
  border: 1px solid #1f293d;
  border-radius: 8px;
  padding: 14px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #a5f3fc;
  overflow-x: auto;
  line-height: 1.6;
}}
footer {{
  text-align: center;
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--text-muted);
  padding: 20px 0;
  border-top: 1px solid var(--panel-border);
}}
</style>
</head>
<body>
<div class="container">
  <header>
    <div class="logo-title">
      <h1>CHUN-COCO // QUANT AUDIT DESK</h1>
      <div style="display:flex; gap:8px; align-items:center; margin-top:6px;">
        <span class="badge-live">LIVE TELEMETRY (EC2)</span>
        <span style="font-family:'JetBrains Mono'; font-size:11px; color:var(--text-muted);">Antigravity V9.99 + Gemini Quant V2.2</span>
      </div>
    </div>
    <div style="display:flex; gap:10px; align-items:center;">
      <span class="user-badge">🔓 {role}</span>
    </div>
  </header>

  <div class="stats-grid">
    <div class="card">
      <div class="label">Anchor USDT Balance</div>
      <div class="value text-cyan">${balance}</div>
      <div class="sub">Binance Futures /fapi/v2/balance</div>
    </div>
    <div class="card">
      <div class="label">Manual Adopted PnL</div>
      <div class="value text-green">+{manual_pnl:.4f} USDT</div>
      <div class="sub">TRUMPUSDT (modo="adoptada")</div>
    </div>
    <div class="card">
      <div class="label">Capital Transfer Anchor</div>
      <div class="value text-gold">+{transfer_amt:.4f} USDT</div>
      <div class="sub">Principal deposit tranId: 426772998892</div>
    </div>
    <div class="card">
      <div class="label">Git Tree Verification</div>
      <div class="value text-cyan">{commit_sha}</div>
      <div class="sub">SHA-256 Merkle Chain Anchor</div>
    </div>
  </div>

  <div class="main-grid">
    <div class="card">
      <div class="section-title">🛡️ Cryptographic Manifest Roots (Grade B/A Intake)</div>
      <div style="margin-bottom:8px; font-size:12px; color:var(--text-muted);">Root Manifest Hash (SHA-256):</div>
      <div class="hash-box">{root_sha}</div>
      <div style="margin-bottom:8px; font-size:12px; color:var(--text-muted);">Timestamp UTC:</div>
      <div class="hash-box">{gen_time}</div>
      <div style="margin-top:12px; font-size:12px; color:var(--text-muted); line-height:1.5;">
        Audit standard for <strong>@eveescout</strong> and automated quant intake crawlers. Commits generated hourly via cron on AWS EC2 node.
      </div>
    </div>

    <div class="card">
      <div class="section-title">📂 Public Unauthenticated Data Feeds</div>
      <div class="endpoints-list">
        <a href="/manifest_sha256.json" target="_blank">
          <span>manifest_sha256.json</span>
          <span class="copy-pill">JSON</span>
        </a>
        <a href="/income_ledger.json" target="_blank">
          <span>income_ledger.json (Classified)</span>
          <span class="copy-pill">100 Records</span>
        </a>
        <a href="/user_trades.json" target="_blank">
          <span>user_trades.json (Receipts)</span>
          <span class="copy-pill">12 Symbols</span>
        </a>
        <a href="/balance_anchor.json" target="_blank">
          <span>balance_anchor.json (Reconciliation)</span>
          <span class="copy-pill">USDT</span>
        </a>
      </div>
    </div>
  </div>

  <div class="card" style="margin-bottom:24px;">
    <div class="section-title">🤖 Direct Machine Intake for @eveescout Automated Crawler</div>
    <p style="font-size:12px; color:var(--text-muted); margin-bottom:12px;">
      Direct unauthenticated HTTP GET endpoints (no token gate, no human-in-the-loop required):
    </p>
    <div class="curl-box">
curl -s https://mechanics-category-hereby-shareware.trycloudflare.com/manifest_sha256.json<br>
curl -s https://mechanics-category-hereby-shareware.trycloudflare.com/income_ledger.json<br>
curl -s https://mechanics-category-hereby-shareware.trycloudflare.com/user_trades.json
    </div>
  </div>

  <footer>
    Chun-coco Autonomous Trading Desk // Verified Public Telemetry Node // AWS EC2 13.53.36.244
  </footer>
</div>
</body>
</html>
"""
    return html

class SecureTelemetryHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query_params = urllib.parse.parse_qs(parsed.query)

        token, role = check_auth(self.headers, query_params)
        display_role = role or "Public Quant Verifier"

        # Serve public JSON files directly (Unauthenticated allowed for verifier crawlers)
        safe_files = {
            '/manifest_sha256.json': 'manifest_sha256.json',
            '/income_ledger.json': 'income_ledger.json',
            '/user_trades.json': 'user_trades.json',
            '/balance_anchor.json': 'balance_anchor.json'
        }

        if path in safe_files:
            fpath = os.path.join(REPO_DIR, safe_files[path])
            if os.path.exists(fpath):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(fpath, 'rb') as fp:
                    self.wfile.write(fp.read())
                return

        if path.startswith('/snapshots/') and path.endswith('.json'):
            fname = os.path.basename(path)
            fpath = os.path.join(REPO_DIR, 'snapshots', fname)
            if os.path.exists(fpath):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                with open(fpath, 'rb') as fp:
                    self.wfile.write(fp.read())
                return

        # Serve visual dashboard at root
        if path == '/' or path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(get_html_dashboard(token or "public", display_role).encode('utf-8'))
            return

        self.send_error(404, "File Not Found")

def run_server():
    server = HTTPServer(('127.0.0.1', PORT), SecureTelemetryHandler)
    print(f"Chun-coco Telemetry Server listening on 127.0.0.1:{PORT}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()
