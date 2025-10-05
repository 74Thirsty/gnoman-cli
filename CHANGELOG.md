# Changelog

All notable changes to **GNOMAN CLI** will be documented here.
This project follows [Semantic Versioning](https://semver.org/) rules.

---

## [Unreleased]

## [1.1.0] — Rebuild & Restoration

### Restored
* Mission-control dashboard (Textual-based).
* Wallet, Safe, and Audit subsystems.
* Drift detection and sync view.
* Real-time forensic logging.

### Removed
* Temporary CLI-only architecture introduced in 1.0.0.

### Added
* Cross-platform keyring adapter layer.
* Encrypted export/import using passphrase-protected JSON.

---

## [0.3.0] — 2025-10-01

### Added

* Cross-environment `gnoman sync` with drift detection and reconciliation flags.
* Forensic audit pipeline producing signed JSON/PDF snapshots under `~/.gnoman/audits/`.
* Transaction simulator upgrades with local fork tracing, ML toggles, and plugin-aware autopilot orchestration.
* Incident recovery suite: `gnoman rescue safe`, `gnoman rotate all`, and `gnoman freeze` controls.
* Restored the original menu-driven Safe, Wallet, and Key Manager features within the packaged CLI.

### Changed

* Rotating forensic log now lives at `~/.gnoman/logs/gnoman.log`.
* Curses TUI highlights new mission control panels for sync, graph, autopilot, and recovery tooling.

---

## [0.2.0] — 2025-09-20

### Added

* Argparse-powered mission control CLI with `safe`, `tx`, `secrets`, `audit`, `guard`, and `plugin` command groups.
* Stub handlers that emit structured dicts and JSON log lines via the rotating logbook at `~/.gnoman/gnoman.log`.
* Curses mission control TUI scaffold launched by default when no subcommand is supplied.

### Changed

* `python -m gnoman` now opens the TUI unless a subcommand is provided.

---

## \[0.1.4] — 2025-09-06

### Changed

* **Critical update:** `gnoman/data/GnosisSafe.json` (Safe v1.3.0 ABI) is now bundled.
* Fixed Safe initialization: methods `getOwners`, `getThreshold`, and `getGuard` now resolve correctly.
* Improved ABI path resolution to work regardless of script location.

---

## \[0.1.3] — 2025-09-03

### Added

* Forensic audit log hardened with hash chaining + optional HMAC integrity checks.
* 24h transaction hold (`safe_hold.json`) with persistence across sessions.
* Delegate registry (`safe_delegates.json`) mapping owners → delegates.

---

## \[0.1.2] — 2025-08-30

### Added

* Wallet Manager: mnemonic import/export, hidden HD tree with optional passphrase.
* Address labeling and JSON export (`wallet_export.json`).
* System keyring integration for secure mnemonic storage.

---

## \[0.1.1] — 2025-08-27

### Added

* Gnosis Safe core actions: add/remove owners, change threshold, fund Safe with ETH.
* Execute Safe transactions with multiple signatures.
* Guard enable/disable toggles.
* Wallet derivation and preview (default + custom paths).

---

## \[0.1.0] — 2025-08-25

### Initial Release

* Standalone CLI (`core.py`) with Safe, Wallet, and Key Manager menus.
* Web3 bootstrap with retry logic and audit logging.
* Key manager: add/get/delete/list secrets in system keyring.
* ASCII splash banner + startup logging.
