
---

# GNOMAN: Guardian of Safes, Master of Keys

![Sheen Banner](https://raw.githubusercontent.com/74Thirsty/74Thirsty/main/assets/gnoman.svg)

---

![Docker Pulls](https://img.shields.io/docker/pulls/gadgetsaavy/gnoman?style=for-the-badge\&logo=docker\&color=2496ED)
![Docker Image Size (tag)](https://img.shields.io/docker/image-size/gadgetsaavy/gnoman/latest?style=for-the-badge\&logo=docker\&color=0db7ed)
![PyPI](https://img.shields.io/pypi/v/gnoman-cli?style=for-the-badge\&logo=python\&color=3776AB)
![GitHub Repo stars](https://img.shields.io/github/stars/74Thirsty/gnoman-cli?style=for-the-badge\&logo=github\&color=181717)

**GNOMAN** is a mission-control console for multisig operators, Safe guardians, and incident responders. It combines scriptable CLI commands, a curses dashboard, cross-environment secret sync, and structured forensic logging so every wallet, Safe, and ABI interaction leaves a permanent trace.

---

## ✨ What’s New in v1.x

GNOMAN has evolved far beyond Safe proposals. The latest versions now include:

* **Full Safe lifecycle orchestration** (deploy, propose, sign, exec, rotate).
* **HD wallet tree with custom derivation paths** (including vanity address generation and QR export).
* **Cross-environment secret sync** across keyring, `.env`, and remote vaults with drift reconciliation.
* **Audit mode** producing signed JSON + PDF forensic reports of balances, owners, thresholds, and expiring secrets.
* **Graph visualization** of arbitrage routes and liquidity maps with neon styling.
* **Autopilot pipeline** integrating simulation, ML validation, Safe payload prep, and execution.
* **Guard daemon** for continuous monitoring (secrets, balances, quorum health, arbitrage alerts).
* **Rescue and recovery toolkit** for quorum loss, wallet freezes, and emergency rotation.
* **Plugin hot-swapping** with schema enforcement and version history tracking.
* **ABI orchestration** for consistent, enforceable calldata encoding across all plugin and Safe actions.

---

## 🚀 Mission Control CLI

Launch with:

```bash
python -m gnoman --help
```

### Safe lifecycle

```bash
gnoman safe propose --to <addr> --value <eth> --data <calldata>
gnoman safe sign <proposal-id>
gnoman safe exec <proposal-id>
gnoman safe status <SAFE_ADDR>
gnoman safe rotate-owner <SAFE_ADDR> <old> <new>
```

### Wallet operations

```bash
gnoman wallet derive <path>
gnoman wallet vanity --pattern 0xDEAD
gnoman wallet export --qr
gnoman wallet rotate <WALLET_ID>
```

### Transaction simulation & autopilot

```bash
gnoman tx simulate <proposal-id> [--plan plan.json] [--trace]
gnoman autopilot [--dry-run | --execute | --alerts-only] [--plan plan.json]
```

### Secret management

```bash
gnoman secrets list
gnoman secrets add <KEY> <VALUE>
gnoman secrets rotate <KEY>
gnoman secrets rm <KEY>
```

### Cross-environment sync

```bash
gnoman sync [--force | --reconcile]
```

Synchronizes keyring, `.env`, and remote vaults. Drift is logged and can be forced or reconciled.

### Forensics and monitoring

```bash
gnoman audit
gnoman guard --cycles 5
```

`gnoman audit` produces a signed JSON+PDF report in `~/.gnoman/audits/`.
`gnoman guard` runs continuous monitoring, dispatching alerts via Discord/Slack/PagerDuty.

### Graph visualisation

```bash
gnoman graph view --format svg --output ~/.gnoman/graphs/
```

### Incident recovery

```bash
gnoman rescue safe <SAFE_ADDR>
gnoman rotate all
gnoman freeze <wallet|safe> <id> [--reason text]
```

### Plugin management

```bash
gnoman plugin list
gnoman plugin add <name>
gnoman plugin remove <name>
gnoman plugin swap <name> <version>
```

### ABI orchestration

```bash
gnoman abi load <path/to/abi.json>
gnoman abi encode <function> <args>
gnoman abi verify <payload>
```

---

## 🎛️ Terminal UI

Running `python -m gnoman` with no subcommand launches the curses mission control dashboard.
Panels include: **Safe, Wallet, Tx, Secrets, Sync, Audit, Graph, Autopilot, Rescue, Plugin, Guard, ABI.**
Hotkeys provide rapid switching; logs and alerts are streamed live.

---

## 🛠️ Development

* Python 3.10+
* Install with:

  ```bash
  pip install -e .
  ```
* Logs are written to `~/.gnoman/logs/gnoman.log`. Remove to reset.
* Run `python -m gnoman safe --help` or `python -m gnoman wallet --help` for module-specific options.

---

🔐 **GNOMAN** is the guardian of safes and master of keys: a single cockpit for secrets, wallets, multisigs, and forensic truth.
