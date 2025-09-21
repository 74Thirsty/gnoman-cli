![Sheen Banner](https://raw.githubusercontent.com/74Thirsty/74Thirsty/main/assets/gnoman.svg)

---

# GNOMAN: Guardian of Safes, Master of Keys

![Docker Pulls](https://img.shields.io/docker/pulls/gadgetsaavy/gnoman?style=for-the-badge\&logo=docker\&color=2496ED)
![Docker Image Size (tag)](https://img.shields.io/docker/image-size/gadgetsaavy/gnoman/latest?style=for-the-badge\&logo=docker\&color=0db7ed)
![PyPI](https://img.shields.io/pypi/v/gnoman-cli?style=for-the-badge\&logo=python\&color=3776AB)
![GitHub Repo stars](https://img.shields.io/github/stars/74Thirsty/gnoman-cli?style=for-the-badge\&logo=github\&color=181717)

**GNOMAN** is a standalone command-line toolkit for those who demand uncompromising control over digital assets. It’s the forge where wallets, safes, and keys are shaped into reliable, battle-tested tools.

### Core Functions

**1. Gnosis Safe Management**
Direct, auditable interaction with your Safe. Deploy new vaults, set thresholds, rotate owners, propose or execute transactions—all without tangled dashboards or risky browser extensions.

**2. Wallet Management**
Generate, rotate, import, or export wallets with full HD derivation tree support. Build hidden branches, use throwaway wallets, store cold, or export JSONs. GNOMAN gives you the flexibility of hardware ecosystems while keeping you in control of the root keys.

**3. Key Manager & Backup**
Secrets are preserved with a strict order: **keyring → .env.secure → environment → prompt**. Once a key is seen, it is persisted. If one layer fails, the next holds. Backups use AES-GCM encryption for resilience without plaintext leakage.

### Why GNOMAN Exists

Crypto tools are often too casual (browser plugins) or too arcane (raw JSON-RPC). GNOMAN bridges the gap—terminal-native, structured, auditable, and forensic-grade. Like the gnomon of a sundial, it stands straight in chaos, casting clear lines of truth.

### Features

* Full Safe control: deploy, manage owners, set thresholds.
* Wallet creation, imports, hidden derivations.
* Key persistence and secure backups.
* Interactive menus or fully scriptable flags.
* Verbose debug or silent automation modes.

### Security Philosophy

No invisible storage. No silent failures. No hidden assumptions. GNOMAN enforces explicitness, persistence, and resilience—so your keys, safes, and actions remain under your control.


## Mission Control CLI (v0.2)

GNOMAN now ships with a mission-control style interface inspired by the spec above. Use scriptable commands for automation or drop into the curses dashboard when you want a tactile overview.

### Primary commands

```bash
gnoman safe propose --to <addr> --value <eth> --data <calldata>
gnoman safe sign <proposal-id>
gnoman safe collect <proposal-id>
gnoman safe exec <proposal-id>
gnoman safe status <SAFE_ADDR>

gnoman tx simulate <proposal-id>

gnoman secrets list
gnoman secrets add <KEY> <VALUE>
gnoman secrets rotate <KEY>
gnoman secrets audit

gnoman audit
gnoman guard --transport discord --transport email

gnoman plugin list
gnoman plugin add <name>
gnoman plugin remove <name>
```

### Interactive dashboard

Running `gnoman` without arguments (or with `--tui`) launches a curses interface that mirrors the wireframes in the design document: Safe dashboards, masked secrets view, transaction simulation summary, and plugin management all live behind hotkeys so operators can see state at a glance.


# Quick start (first run)

1. **After making it executable, Run it**

```
python3 gnosis.py
```

2. **Banner shows, then you’ll see the Main Menu**

```
1) Safe Manager (Gnosis Safe)
2) Wallet Manager (HD / hidden trees)
3) Key Manager (Secrets)
4) Exit
```

3. **Secrets resolution (how prompts work)**

* The tool always looks for secrets in this order:
  **keyring ➜ .env/.env.secure ➜ prompt**
* If it asks for something like `RPC_URL` or `OWNER_PRIVATE_KEY`, it means it **didn’t** find it in keyring or env. When you enter it, it is **persisted immediately** to **keyring** (primary) and mirrored to **.env.secure** (chmod 600). Next launch, it won’t ask again unless you delete/rename the keyring entry or change service.

4. **Keyring “service” name**

* Whenever you use Key Manager to set/get/delete/sync a secret, you’ll be asked for a **Service name**.
  Default is `gnoman`. Enter a custom service if you want to silo contexts (e.g., `prod`, `staging`, `personal`).
* Internally, secrets are stored as: `(service, key) -> value`.
* If you want **the Safe/Wallet subsystems** to load from a non-default service every time, set this env before launching:

  ```
  export KEYRING_SERVICE=prod
  python3 gnosis.py
  ```

  (Or just keep using the default `gnoman` service in the prompts.)

---

# Key Manager (Secrets)

**Main Menu → 3) Key Manager**

You’ll use this to seed everything so the app never nags you again.

Typical keys you’ll set:

* `RPC_URL` – your HTTPS RPC endpoint
* `CHAIN_ID` – e.g., `1` for mainnet (optional; defaults to 1)
* `GNOSIS_SAFE` – your Safe address (checksummed)
* `OWNER_PRIVATE_KEY` – hex (with or without `0x`, both accepted)

Menu items:

* **Add/Update secret**: enter key name (e.g., `RPC_URL`), then value, then service (default `gnoman`). This writes to **keyring** and mirrors into **.env.secure**.
* **Retrieve secret**: confirm what’s stored (useful to verify typos).
* **Delete secret**: removes from keyring for that service.
* **List `.env.secure`**: shows a masked view of what’s mirrored locally.
* **Sync `.env.secure → keyring`**: bulk import any `.env.secure` pairs into keyring for a chosen service.

> Tip: If you ever see a prompt for a value you know is in your keyring, you either typed a different **service** than where it’s stored, or `KEYRING_SERVICE` env is set to a different service. Stick to one.

---

# Safe Manager (Gnosis Safe)

**Main Menu → 1) Safe Manager**

On first entry, if needed the tool will prompt for:

* `RPC_URL`
* `GNOSIS_SAFE`
* `OWNER_PRIVATE_KEY`

It writes them to keyring + .env.secure right away. If any value is invalid (bad address/PK), it prints a clear error and returns you to the **Safe menu** (no silent exit). All events are logged to the log file (e.g., `gnoman.log`).

### Safe menu actions

1. **Show Safe info**

* Displays: owners (checksummed), threshold, nonce, ETH balance.
* Good sanity check that you’re pointed at the correct Safe.

2. **Fund Safe with ETH**

* Sends ETH from your `OWNER_PRIVATE_KEY` (the EOA signer) to the Safe.
* Enter an amount like `0.5`. Gas is estimated + padded. EIP-1559 compatible.

3. **Send ERC-20 to Safe**

* Prompts for token address, fetches `symbol/decimals` (falls back if contract is non-standard), and sends tokens **to the Safe** via `transfer`.

4. **Execute Safe transaction (execTransaction)**

* Prompts for `to`, `value (ETH)`, `data (0x…)`, and `operation (0 or 1)`.
* Computes the **exact SafeTx hash** via `getTransactionHash(...)`.
* Signs that hash with your `OWNER_PRIVATE_KEY` and submits `execTransaction`.
* If your Safe has threshold > 1 and you only have one sig, you’ll need to run a multi-sig collection flow (this CLI supports the single-sig immediate execution path; for multi-sig you can still use this to compute and sign then feed additional signatures by extending the packed sig flow—happy to wire that next if you want).

5. **Admin: Add owner**

* Adds an owner, preserving the current threshold.

6. **Admin: Remove owner**

* Removes an owner. Requires **prevOwner address** (Safe maintains a linked list). If you don’t know the previous, you can get it from the Safe’s `getOwners()` plus on-chain linked list order. (If that’s a pain, I can expose a helper that finds the correct `prevOwner` for you.)

7. **Admin: Change threshold**

* Sets a new `threshold` (must be ≥1 and ≤ number of owners).

8. **Guard: Enable 24h withdrawal hold**

* This uses `setGuard(guardAddress)` on the Safe.
* You’ll be prompted for the **DelayGuard** address (the contract you deploy—see below). The address is persisted as `SAFE_DELAY_GUARD`.
* After enabling, **any execTransaction will be forced to queue** for 24 hours before it can succeed.

9. **Guard: Disable withdrawal hold**

* Calls `setGuard(0x0)`. Removes the delay enforcement.

10. **Guard: Show guard status**

* Reads `getGuard()` and prints the active guard address (or “none”).

11. **Back**

* Returns to the main menu.

### How the 24-hour hold actually behaves

* With the guard active, **the first attempt** to execute any Safe transaction **will revert** with a message like `DelayGuard: queued, try again after 24h`.
  That revert is **expected** — it’s how the guard records/queues the tx hash & timestamp.
* **Re-submit the exact same transaction** (same calldata, same to/value/data/op & gas fields) **after 24 hours**. It will then execute normally.
* If you alter anything (e.g., value or calldata), it’s a different hash and will be queued again.

> Pro move: Use the Safe menu option (4) to build the tx. If you’ll re-run it after 24h, keep the exact same parameters.

### Deploying the DelayGuard

If you used the provided `DelayGuard.sol`:

* Deploy it with the Safe address in the constructor (via Remix/Foundry/Hardhat).
* Take the deployed address and enable it using menu item **8**.
* If you later want to switch back to instant withdrawals, disable with **9**.

---

# Wallet Manager (HD / Hidden trees)

**Main Menu → 2) Wallet Manager**

The wallet subsystem is **local-first** and supports both **private key** and **mnemonic (BIP-39)** flows. It doesn’t co-mingle with the Safe — different worlds, clean separation.

### Storage model

* Encrypted store: `wallets.enc` (AES-GCM).
* On start, it asks for **Master password** to decrypt (or creates a new store).
* Inside the store, each wallet entry can contain either a private key or a mnemonic + derivation path.
* You may optionally **store mnemonic in keyring** as well (prompted).

### Menus

1. **Import mnemonic (default acct 0)**

   * Paste your seed phrase.
   * It derives **account 0** at `m/44'/60'/0'/0/0` and prints that address.
   * You can also choose to save the mnemonic to keyring (recommended if you want the Tool to auto-use it later without re-typing the master password).

2. **Scan first N accounts**

   * Looks at `m/44'/60'/0'/0/0 .. m/44'/60'/0'/0/(N-1)` and prints addresses.
   * This is how you find “that address I used years ago” without needing to remember the index.

3. **Derive specific path**

   * Enter any path (e.g., `m/44'/60'/0'/0/7`, or **hidden tree** like `m/44'/60'/1337'/9/0`).
   * It shows the address for that path.
   * The concept of a **“hidden tree”** is just agreeing on a non-standard account branch. This menu lets you derive them all day without users needing to know the theory — they just paste a path string and get an address.

4. **Export discovered addresses to JSON**

   * Writes `hd_export.json` with every path/address you scanned (plus labels if you added any). Great for audits or migrations.

5. **Back**

> TIP: If you imported a mnemonic elsewhere and ended up on, say, path `/0/1` instead of `/0/0`, that’s totally normal. Many wallets choose different defaults. Use **Scan** to locate the right one, or **Derive** to hit a specific path. Once found, label it in your system and use it consistently.

---

# Example end-to-end flows

### A) Seed everything once so it never prompts again

1. Main → Key Manager → Add/Update:

   * `RPC_URL = https://your.provider`
   * `GNOSIS_SAFE = 0xYourSafe...`
   * `OWNER_PRIVATE_KEY = <hex>` (with or without `0x`)
   * (Optional) `CHAIN_ID = 1`
2. Back to Main → Safe Manager → 1) Show Safe info
   You should see owners/threshold/nonce/balance immediately.

### B) Turn on 24-hour hold

1. Deploy `DelayGuard.sol` with your Safe’s address.
2. Safe Manager → 8) Guard: Enable → paste guard address.
   The guard is now active.
3. Try any Safe tx (e.g., fund a contract from Safe): first attempt reverts with “queued”.
4. Re-submit the **same** tx after 24 hours → it executes.

### C) Import a mnemonic and locate a known address

1. Wallet Manager → 1) Import mnemonic → paste phrase.
2. Choose whether to store mnemonic in keyring.
3. Wallet Manager → 2) Scan first N → try N=20.
4. Find the address you recognize.
5. (Optional) Derive a specific path to jump directly.

---

# Troubleshooting

* **“It’s asking for RPC\_URL again.”**
  You likely have secrets in a **different keyring service** than you’re using now.

  * Check with Key Manager → Retrieve secret → *Service name* = `gnoman` (or the one you used).
  * Or set `export KEYRING_SERVICE=that_service` before running.
  * The tool always prefers keyring; if nothing found there, it checks `.env/.env.secure`; if nothing, it prompts.

* **“It exited after I typed a secret.”**
  The current build **does not exit** on successful secret entry. If you see an exit:

  * You probably hit an **invalid address** (non-checksummed/short) or **invalid private key**; the tool logs the precise reason and returns to menu.
  * Check the log file in your working directory (e.g., `gnoman.log`). Errors include stack context and the function that failed.

* **“Guard enabled, but tx still executes instantly.”**

  * Ensure the Safe’s guard shows your guard address (Safe Manager → 10).
  * Ensure your guard was deployed **with your Safe address** in its constructor.
  * You must **retry the same tx after 24 hours** — first attempt *always* reverts to queue it.

* **“Remove owner asks for prevOwner — what is that?”**
  Gnosis Safe keeps a linked list of owners. `prevOwner` is the address that comes “before” the one you’re removing in that list. If you don’t know it, I can add a helper to find it for you programmatically.

---

# Security tips (the “don’t burn yourself” section)

* **Owner private key** is hot in this CLI. Use minimal balances on the EOA — keep the **bulk of assets in the Safe**.
* When enabling the guard, make sure you **don’t lock yourself out** of urgent actions. You can always disable the guard (with current threshold/owners), but the 24-hour delay will apply to that call, too, once queued. Plan signers accordingly.
* `.env.secure` is permissioned `600`, but it’s still a file. **Keyring** is your primary secret store.

---

# Where to go next

You’re fully armed now:

* Keyring primed, `.env.secure` mirrored, no recurrent prompts.
* Safe Manager can fund, send tokens, execute tx, manage owners/threshold, and toggle the 24h guard.
* Wallet Manager handles HD derivations, “hidden tree” paths, imports/exports, and encrypted local storage.


**Critical Update — ABI File Required**

This update introduces a mandatory dependency on the full Gnosis Safe ABI.
The file abi/GnosisSafe.json must now be present in the project root (~/Apps/gnoman-cli/abi/) for all Safe-related functions to work.

Without this file, core features (getOwners, getThreshold, getGuard, execTransaction, etc.) will fail with ABI resolution errors.

This is a blocking requirement for anyone pulling or running core.py. Ensure you have synced the latest repo state and the abi/ directory before running GNOMAN.


---

## License

GNOMAN is **proprietary software**. No person, entity, or organization may use, copy, or execute GNOMAN without an original paper license signed in ink by the Licensor.

* 📜 [Full License Terms](./LICENSE.md) — the complete GNOMAN License Agreement.
* 🖋 [Licensed Parties](./LICENSEE.md) — current holders of license get this.

Electronic signatures, receipts, or downloads do **not** constitute a license.
If your name does not appear in the **LICENSEE.md** registry, you have no rights to GNOMAN.
