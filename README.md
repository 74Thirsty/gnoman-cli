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

## ✨ Mission control at a glance

* **Safe lifecycle orchestration** &mdash; deploy, fund, execute, rotate owners, manage guard delegates, and enforce
  24&nbsp;hour holds directly from the CLI.
* **Wallet and key management** &mdash; derive HD trees, reveal hidden branches, label and export accounts, rotate
  executors, and chase vanity patterns without leaving the terminal.
* **Autopilot + simulation** &mdash; reconcile plugin versions, load plan JSON, run ML-enabled simulations, and execute
  proposals once guardrails are satisfied.
* **Incident response** &mdash; rescue compromised Safes, freeze entities, rotate quorums, and monitor balances and
  quorum health with the guard daemon.
* **Secret management** &mdash; keyring-first resolution, drift detection, reconciliation, and rotation across keyring,
  `.env`, and remote vault mirrors.
* **Forensic reporting** &mdash; signed JSON (and optional PDF) dossiers of Safe state, wallet derivations, plugin
  history, and expiring secrets for compliance.
* **ABI and graph tooling** &mdash; inspect bundled schemas, validate overrides, encode calldata, and export neon graph
  visualisations for routes, owners, and plan flows.

---

## 🚀 Mission control CLI

Launch the CLI with:

```bash
python -m gnoman --help
```

### Safe lifecycle

```bash
gnoman safe info
gnoman safe fund <ETH> --signer-key EXECUTOR_KEY
gnoman safe erc20 <TOKEN> <AMOUNT> --signer-key EXECUTOR_KEY
gnoman safe add-owner <ADDRESS> --signer-key EXECUTOR_KEY
gnoman safe remove-owner <ADDRESS> <PREVIOUS> --signer-key EXECUTOR_KEY
gnoman safe threshold <VALUE> --signer-key EXECUTOR_KEY
gnoman safe guard show
gnoman safe guard set <DELAY_GUARD> --signer-key EXECUTOR_KEY
gnoman safe guard clear --signer-key EXECUTOR_KEY
gnoman safe delegate list|add <OWNER> <DELEGATE>|remove <OWNER> <DELEGATE>
gnoman safe hold list
gnoman safe hold release <SAFE:NONCE>
gnoman safe tx-hash --to <ADDR> --data <0x...>
gnoman safe exec --to <ADDR> --data <0x...> --signature <SIG> --signer-key EXECUTOR_KEY
```

### Transaction simulation & autopilot

```bash
gnoman tx simulate [<proposal-id>] [--plan plan.json] [--trace] [--ml-off]
gnoman tx exec <proposal-id> [--plan plan.json]
gnoman autopilot [--dry-run | --execute | --alerts-only] [--plan plan.json]
```

### Incident response & monitoring

```bash
gnoman rescue safe [--safe <SAFE_ADDR>]
gnoman rescue status
gnoman rotate all
gnoman freeze <wallet|safe|plugin> <id> [--reason text]
gnoman guard [--cycles 5] [--delay 0.5]
```

### Plugin registry & graph exports

```bash
gnoman plugin list
gnoman plugin add <name> --version <semver> [--schema generic]
gnoman plugin remove <name>
gnoman plugin swap <name> <version>
gnoman plugin toggle <name> --enable|--disable
gnoman graph --format svg --output ~/.gnoman/graphs/ [--highlight ADDRESS]
```

### Wallet operations

```bash
gnoman wallet mnemonic generate
gnoman wallet mnemonic import "word list"
gnoman wallet passphrase set <PASSPHRASE>
gnoman wallet passphrase clear
gnoman wallet accounts
gnoman wallet new <LABEL> [--path template]
gnoman wallet scan [--count 10] [--hidden]
gnoman wallet derive <PATH | template>
gnoman wallet vanity [--prefix 0xabc] [--suffix ff] [--regex pattern] [--max-attempts 100000]
gnoman wallet label <ADDRESS> <LABEL>
gnoman wallet export [--output exported_accounts.json]
```

### Secrets & sync

```bash
gnoman sync status
gnoman sync drift
gnoman sync force
gnoman sync apply <KEY> <keyring|env>
gnoman sync set <KEY> <VALUE>
gnoman sync rotate <KEY>
gnoman sync remove <KEY>

gnoman secrets list
gnoman secrets add <KEY> <VALUE>
gnoman secrets rotate <KEY>
gnoman secrets remove <KEY>
```

Secrets resolve **keyring-first**, fall back to `.env`, and never read from `.env.secure`. Drift detection highlights
mismatches before reconciliation and every action is logged to the forensic ledger.

### Forensic audit & ABI utilities

```bash
gnoman audit
gnoman abi show
gnoman abi validate path/to/abi.json
gnoman abi encode execTransaction --args '["0xdead...",0,"0x",0]' [--address <SAFE_ADDR>]
```

`gnoman audit` generates a signed JSON report covering Safe configuration, derived wallets, plugin state, and secret
metadata in `~/.gnoman/audits/`. ABI helpers inspect bundled and custom ABIs to enforce calldata integrity when
building Safe transactions.

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
