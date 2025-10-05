# GNOMAN: Guardian of Safes, Master of Keys
![Sheen Banner](https://raw.githubusercontent.com/74Thirsty/74Thirsty/main/assets/gnoman.svg)

![Docker Pulls](https://img.shields.io/docker/pulls/gadgetsaavy/gnoman?style=for-the-badge&logo=docker&color=009DDC)
![PyPI](https://img.shields.io/pypi/v/gnoman-cli?style=for-the-badge&logo=python&color=72CDF4)

✨ **What is GNOMAN?**

GNOMAN is a mission-control console for multisig operators, forensic auditors, and DeFi incident responders.
It fuses:
  • A modular command-line interface  
  • A curses-powered dashboard UI  
  • Forensic logging and signed audit trails  
  • Deep integrations with wallets, keyrings, and Gnosis Safes  

GNOMAN replaces a zoo of fragile scripts with a single god-tier control deck.

# 🚀 **Core Features**

🔑 **Secrets & Wallets**
  • Full keyring integration (freedesktop-secrets, macOS Keychain, Windows Credential Locker).  
  • .env / .env.secure drift detection and reconciliation.  
  • HD wallet support with:  
    • Hidden derivation trees  
    • Custom derivation paths  
    • Vanity address generation  
    • Cold wallet / hot executor separation.  
  • Wallet monitoring with real-time balance and nonce tracking.

🏛️ **Safe Orchestration**
  • Deploy new Gnosis Safes with arbitrary owner sets & thresholds.  
  • Add/remove owners, rotate keys, and patch Safe configs live.  
  • Automatic Safe ABI syncing (via ABISchemaManager).  
  • Submit, batch, and simulate transactions across multiple Safes.

🧰 **Contract Toolkit**
  • ABI loading, schema enforcement, and method resolution.  
  • Transaction builder with type-safe argument validation.  
  • Ephemeral executors for flash execution (EIP-6780 friendly).  
  • Gas calibration and automatic fee bumpers.

📊 **Forensic Audit Mode**
  • Crawl wallets, Safes, and secrets into a signed report (JSON/PDF).  
  • Includes:  
    • Wallet balance snapshots  
    • Safe threshold configs  
    • Expiring secrets  
    • Last access timestamps  
  • Reports cryptographically signed with GNOMAN’s audit key.

🧠 **Arbitrage & DeFi Hooks**
  • Plugin loader for loan and trade modules (Uniswap, Balancer, Curve, Aave, etc.).  
  • Canonical schema enforcement for graph + execution steps.  
  • RPZE pathfinding validator integration.  
  • ExecutionManager hooks for cycle watching, memory attach, and readiness checks.

📡 **Sync & Drift Detection**
  • gnoman sync: reconcile secrets across keyring, .env, .env.secure, and remote vaults.  
  • Detect drift and resolve conflicts interactively.

📟 **Dashboard UI**
  • Curses-powered neon cockpit.  
  • Views: diffs, branches, GitHub status, Safe states, audit logs.  
  • Keyboard-driven interactive ops (submit tx, rotate key, reconcile secrets).

# 🔧 **Installation**

From PyPI:

```bash
pip install gnoman-cli
````

From DockerHub:

```bash
docker pull gadgetsaavy/gnoman:latest
docker run -it gadgetsaavy/gnoman
```

From Source:

```bash
git clone https://github.com/74Thirsty/gnoman-cli.git
cd gnoman-cli
pip install -e .
```

# 🕹️ **Usage**

CLI:

```bash
gnoman safe deploy --owners 0xA.. 0xB.. 0xC.. --threshold 2
gnoman wallet derive --path "m/44'/60'/0'/0/1337"
gnoman sync
gnoman audit --output report.pdf
```

Dashboard:

```bash
gnoman tui
```

Navigate with arrow keys. q to quit.

⸻

🔒 **Security Posture**
• All secrets loaded from keyring-first (never plaintext by default).
• Forensic logs signed with GNOMAN’s audit key.
• Ephemeral execution to prevent key leakage.
• Multisig-first design: never trust a single key.

⸻

🛠️ **Roadmap**
• Remote vault sync (Hashicorp Vault, AWS Secrets Manager).
• ML-based anomaly detection in audit mode.
• zk-proof attestation of audit reports.
• Direct Flashbots bundle submission from dashboard.

⸻

📋 **Implementation Reality Check**

The current open-source snapshot uses deterministic fixtures and simulated managers to make the demo experience self-contained. Before treating GNOMAN as production-ready, review the [Implementation Status](docs/IMPLEMENTATION_STATUS.md) report that catalogues the gaps versus the latest developer directive.

⸻

🧑‍💻 **Authors**

Built with obsession by Christopher Hirschauer (</gadget_saavy>).

⸻

### 💸 **Support GNOMAN Development**

If you appreciate the work behind GNOMAN, feel free to **donate** to support the continued development and improvement of this project:

#### PayPal:

[Donate via PayPal](https://www.paypal.me/obeymythirst)

#### Gnosis Safe:

To donate directly to my Gnosis Safe, use the following address:

**Gnosis Safe Address**: `eth:0xC6139506fa54c450948D9D2d8cCf269453A54f17`

---

### **Key Updates**:
1. **PayPal Donation Button**: I added a **PayPal donation link** for you. You can replace `yourusername` with your actual PayPal username.
2. **Gnosis Safe Donation**: I included a placeholder for **your Gnosis Safe address**. You can replace `0xYourGnosisSafeAddressHere` with your actual Gnosis Safe address to allow donations directly to your Safe.

---

### **How to Use**:
- Simply copy the **“PayPal”** and **“Gnosis Safe”** sections into the **README**.
- **Link to your PayPal** and **Gnosis Safe address** so users can contribute directly.
