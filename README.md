![Sheen Banner](https://raw.githubusercontent.com/74Thirsty/74Thirsty/main/assets/gnoman.svg)

---

# GNOMAN: Guardian of Safes, Master of Keys

![Docker Pulls](https://img.shields.io/docker/pulls/gadgetsaavy/gnoman?style=for-the-badge&logo=docker&color=2496ED)
![Docker Image Size (tag)](https://img.shields.io/docker/image-size/gadgetsaavy/gnoman/latest?style=for-the-badge&logo=docker&color=0db7ed)
![PyPI](https://img.shields.io/pypi/v/gnoman-cli?style=for-the-badge&logo=python&color=3776AB)
![GitHub Repo stars](https://img.shields.io/github/stars/74Thirsty/gnoman-cli?style=for-the-badge&logo=github&color=181717)

**GNOMAN** is a mission-control console for multisig operators, Safe guardians, and incident responders. It combines a
scriptable CLI surface, cross-environment secret automation, and structured forensic logging so every wallet, Safe, and
ABI interaction leaves a permanent trace.

---

## ✨ What’s New in v1.x

* **Safe lifecycle orchestration** &mdash; deploy, fund, propose, sign, execute, rotate owners, manage thresholds, and
enforce 24&nbsp;hour holds and guard delegates directly from the CLI.
* **HD wallet tooling** &mdash; derive accounts from labelled paths, surface hidden branches, rotate executors, export QR
payloads, and search for vanity addresses without leaving GNOMAN.
* **Autopilot + transaction simulation** &mdash; load plan JSON, reconcile plugin versions, run ML-enabled simulations, and
optionally execute Safe transactions once guardrails are green.
* **Incident response + guard rails** &mdash; run rescue flows, freeze compromised entities, monitor quorum and balance
health, and dispatch alerts from the guard daemon.
* **Secret management and sync** &mdash; keyring-first secret resolution with drift detection, reconciliation, and rotation
across keyring, `.env`, and remote vault mirrors.
* **Forensic audit reporting** &mdash; produce signed JSON (and optional PDF) dossiers of Safe state, wallet derivations,
plugin history, and expiring secrets for compliance reviews.
* **ABI orchestration and graphing** &mdash; load and validate ABI schemas, encode calldata, and export neon graph visual
isations for plans, owners, and liquidity routes.

---

## 🚀 Mission Control CLI

Launch the CLI with:

```bash
python -m gnoman --help
```

### Safe lifecycle

```bash
gnoman safe info
gnoman safe fund <ETH> --signer-key EXECUTOR_KEY
gnoman safe add-owner <ADDRESS> --signer-key EXECUTOR_KEY
gnoman safe remove-owner <ADDRESS> <PREVIOUS> --signer-key EXECUTOR_KEY
gnoman safe threshold <VALUE> --signer-key EXECUTOR_KEY
gnoman safe guard set <DELAY_GUARD> --signer-key EXECUTOR_KEY
gnoman safe delegate add <OWNER> <DELEGATE>
gnoman safe hold list
```

### Wallet operations

```bash
gnoman wallet mnemonic generate
gnoman wallet new <LABEL> [--path template]
gnoman wallet list [--hidden]
gnoman wallet vanity --prefix 0xabc --max-attempts 100000
gnoman rotate all
```

### Transaction simulation & autopilot

```bash
gnoman tx simulate <proposal-id> [--plan plan.json] [--trace] [--ml-off]
gnoman tx exec <proposal-id> [--plan plan.json]
gnoman autopilot [--dry-run | --execute | --alerts-only] [--plan plan.json]
```

### Incident response & monitoring

```bash
gnoman rescue safe [--safe <SAFE_ADDR>]
gnoman freeze <wallet|safe|plugin> <id> [--reason text]
gnoman guard [--cycles 5]
```

### Plugin registry & graph exports

```bash
gnoman plugin list
gnoman plugin add <name> --version <semver>
gnoman plugin swap <name> <version>
gnoman graph --format svg --output ~/.gnoman/graphs/
```

### Secrets & sync

```bash
gnoman secrets list
gnoman secrets add <KEY> <VALUE>
gnoman secrets rotate <KEY>
gnoman secrets remove <KEY>

gnoman sync status
gnoman sync drift
gnoman sync force
gnoman sync rotate <KEY>
```
Secrets resolve **keyring-first**, fall back to `.env`, and never read from `.env.secure`. Drift detection highlights
mismatches before reconciliation and every action is logged to the forensic ledger.

### Forensic audit & ABI utilities

```bash
gnoman audit
gnoman abi show
gnoman abi encode execTransaction --args '["0xdead...",0,"0x",0]'
```
`gnoman audit` generates a signed JSON report covering Safe configuration, derived wallets, plugin state, and secret
metadata in `~/.gnoman/audits/`. ABI helpers inspect bundled and custom ABIs to enforce calldata integrity when building
Safe transactions.

---

## 🎛️ Terminal UI

Running `python -m gnoman` with no subcommand prints a mission control quick reference that points operators to the
modular CLI command groups. The legacy curses dashboard has been retired; every panel now maps to a CLI surface with
forensic logging baked in.

---

## 🛠️ Development

* Python 3.10+
* Install dependencies with:

  ```bash
  pip install -e .
  ```
* Run `python -m gnoman safe --help` or `python -m gnoman wallet --help` for module-specific options.

Structured logging is written to `~/.gnoman/logs/gnoman.log`. Delete the file to reset forensic history during
local testing.
