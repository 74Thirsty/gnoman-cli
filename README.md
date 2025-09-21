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

GNOMAN v0.2.0 introduces an argparse-powered command surface. Launch it with:

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
gnoman tx simulate <proposal-id>
gnoman tx exec <proposal-id>
```

### Secret management

```bash
gnoman secrets list
gnoman secrets add <KEY> <VALUE>
gnoman secrets rotate <KEY>
gnoman secrets rm <KEY>
```

### Forensics and monitoring

```bash
gnoman audit
gnoman guard
```

### Plugin management

```bash
gnoman plugin list
gnoman plugin add <name>
gnoman plugin remove <name>
```

Every command logs a JSON record to `~/.gnoman/gnoman.log` using a rotating file handler so follow-up tooling can
process GNOMAN activity chronologically.

## Terminal UI

Running `python -m gnoman` with no subcommand launches the curses mission control surface. The scaffolded dashboard displays
hotkeys for Safe, Tx, Secrets, Audit, Guard, and Plugin panels. Press any key to exit the placeholder view.

## Development

* Python 3.10+
* Install dependencies with `pip install -e .`
* Run `python -m gnoman safe --help` to view Safe-specific options.

Structured logging is written to `~/.gnoman/gnoman.log`. Remove the file if you want a clean slate during development.
