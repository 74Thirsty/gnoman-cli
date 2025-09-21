![Sheen Banner](https://raw.githubusercontent.com/74Thirsty/74Thirsty/main/assets/gnoman.svg)

---

# GNOMAN: Guardian of Safes, Master of Keys

![Docker Pulls](https://img.shields.io/docker/pulls/gadgetsaavy/gnoman?style=for-the-badge&logo=docker&color=2496ED)
![Docker Image Size (tag)](https://img.shields.io/docker/image-size/gadgetsaavy/gnoman/latest?style=for-the-badge&logo=docker&color=0db7ed)
![PyPI](https://img.shields.io/pypi/v/gnoman-cli?style=for-the-badge&logo=python&color=3776AB)
![GitHub Repo stars](https://img.shields.io/github/stars/74Thirsty/gnoman-cli?style=for-the-badge&logo=github&color=181717)

**GNOMAN** is a mission-control console for multisig operators and incident responders. It combines scriptable CLI
commands, a curses dashboard, and structured forensic logging so every Safe interaction leaves a trace.

## Mission Control CLI

GNOMAN now ships a modular CLI that mirrors the original `tools/core.py` feature set. Launch it with:

```bash
python -m gnoman --help
```

### Safe lifecycle

```bash
gnoman safe info
gnoman safe fund <ETH> --signer-key EXECUTOR_KEY
gnoman safe add-owner <ADDRESS> --signer-key EXECUTOR_KEY
gnoman safe guard set <DELAY_GUARD> --signer-key EXECUTOR_KEY
```

### Wallet management

```bash
gnoman wallet mnemonic generate
gnoman wallet new <LABEL> [--path template]
gnoman wallet scan [--count 10] [--hidden]
gnoman wallet vanity --prefix 0xabc --max-attempts 100000
```

### Secret synchronisation

```bash
gnoman sync status
gnoman sync drift
gnoman sync force
gnoman sync rotate RPC_URL
```
Secrets are resolved keyring-first with `.env` as fallback. Drift detection highlights mismatched values before you reconcile.

### Forensic audit

```bash
gnoman audit
```
Generates a signed JSON and PDF report covering Safe configuration, derived wallets, and secret metadata. Output is stored in `~/.gnoman/audits/`.

### ABI utilities

```bash
gnoman abi show
gnoman abi encode execTransaction --args '["0xdead...",0,"0x",0]'
```
Inspect the bundled Safe ABI, validate overrides, and encode calldata with forensic logging.

## Terminal UI

The curses dashboard has been retired in favour of the CLI. Running `python -m gnoman` now prints a quick reference pointing to the `safe`, `wallet`, `sync`, `audit`, and `abi` command groups.

## Development

* Python 3.10+
* Install dependencies with `pip install -e .`
* Run `python -m gnoman safe --help` to view Safe-specific options.

Structured logging is written to `~/.gnoman/logs/gnoman.log`. Remove the file if you want a clean slate during development.
