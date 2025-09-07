# Changelog

All notable changes to **GNOMAN CLI** will be documented here.
This project follows [Semantic Versioning](https://semver.org/) rules.

---

## \[0.1.4] — 2025-09-06

### Changed

* **Critical update:** `abi/GnosisSafe.json` (Safe v1.3.0 ABI) is now required.
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
