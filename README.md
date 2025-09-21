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

GNOMAN v0.3.0 expands the argparse-powered surface with sync, graphing, autopilot, and incident recovery workflows. Launch it with:

```bash
python -m gnoman --help
```

### Safe lifecycle

```bash
gnoman safe propose --to <addr> --value <eth> --data <calldata>
gnoman safe sign <proposal-id>
gnoman safe exec <proposal-id>
gnoman safe status <SAFE_ADDR>
```

### Transaction operations

```bash
gnoman tx simulate [<proposal-id>] [--plan path.json] [--trace] [--ml-off]
gnoman tx exec <proposal-id>
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
Synchronise keyring, `.env`, `.env.secure`, and remote vault entries. Drift can be resolved interactively or forced to the AES priority order.

### Simulation and autopilot

```bash
gnoman tx simulate ...
gnoman autopilot [--dry-run | --execute | --alerts-only] [--plan plan.json]
```
The autopilot pipeline fetches loans, builds trades, validates with ML, prepares Safe payloads, simulates on an Anvil fork, and queues, alerts, or executes depending on flags.

### Forensics and monitoring

```bash
gnoman audit
gnoman guard --cycles 5
```
`gnoman audit` produces a signed JSON+PDF snapshot in `~/.gnoman/audits/`. `gnoman guard` runs the System Guardian daemon to check secrets, balances, quorum, gas, and arbitrage opportunities, dispatching alerts to Discord/Slack/PagerDuty.

### Graph visualisation

```bash
gnoman graph view [--format svg|png|html] [--output custom/path]
```
Renders AES GraphManager output with neon-highlighted profitable routes. Assets are stored in `~/.gnoman/graphs/` by default.

### Incident recovery

```bash
gnoman rescue safe <SAFE_ADDR>
gnoman rotate all
gnoman freeze <wallet|safe> <id> [--reason text]
```
Recovery tooling walks operators through Safe quorum loss, rotates all wallets/owners, and freezes compromised entities until an explicit unfreeze event.

### Plugin management

```bash
gnoman plugin list
gnoman plugin add <name>
gnoman plugin remove <name>
gnoman plugin swap <name> <version>
```
Hot-swapping records schema validation and maintains a forensic history of plugin versions used by transactions.

## Terminal UI

Running `python -m gnoman` with no subcommand launches the curses mission control surface. The scaffolded dashboard displays
hotkeys for Safe, Tx, Secrets, Sync, Audit, Graph, Autopilot, Rescue, Plugin, and Guard panels. Press any key to exit the placeholder view.

## Development

* Python 3.10+
* Install dependencies with `pip install -e .`
* Run `python -m gnoman safe --help` to view Safe-specific options.

Structured logging is written to `~/.gnoman/logs/gnoman.log`. Remove the file if you want a clean slate during development.
