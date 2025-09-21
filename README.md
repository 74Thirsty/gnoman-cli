GNOMAN: Guardian of Safes, Master of Keys


⸻

✨ What is GNOMAN?

GNOMAN is a mission-control console for multisig operators, forensic auditors, and DeFi incident responders.
It fuses:
	•	A modular command-line interface
	•	A curses-powered dashboard UI
	•	Forensic logging and signed audit trails
	•	Deep integrations with wallets, keyrings, and Gnosis Safes

GNOMAN replaces a zoo of fragile scripts with a single god-tier control deck.

⸻

🚀 Core Features

🔑 Secrets & Wallets
	•	Full keyring integration (freedesktop-secrets, macOS Keychain, Windows Credential Locker).
	•	.env / .env.secure drift detection and reconciliation.
	•	HD wallet support with:
	•	Hidden derivation trees
	•	Custom derivation paths
	•	Vanity address generation
	•	Cold wallet / hot executor separation.
	•	Wallet monitoring with real-time balance and nonce tracking.

🏛️ Safe Orchestration
	•	Deploy new Gnosis Safes with arbitrary owner sets & thresholds.
	•	Add/remove owners, rotate keys, and patch Safe configs live.
	•	Automatic Safe ABI syncing (via ABISchemaManager).
	•	Submit, batch, and simulate transactions across multiple Safes.

🧰 Contract Toolkit
	•	ABI loading, schema enforcement, and method resolution.
	•	Transaction builder with type-safe argument validation.
	•	Ephemeral executors for flash execution (EIP-6780 friendly).
	•	Gas calibration and automatic fee bumpers.

📊 Forensic Audit Mode
	•	Crawl wallets, Safes, and secrets into a signed report (JSON/PDF).
	•	Includes:
	•	Wallet balance snapshots
	•	Safe threshold configs
	•	Expiring secrets
	•	Last access timestamps
	•	Reports cryptographically signed with GNOMAN’s audit key.

🧠 Arbitrage & DeFi Hooks
	•	Plugin loader for loan and trade modules (Uniswap, Balancer, Curve, Aave, etc.).
	•	Canonical schema enforcement for graph + execution steps.
	•	RPZE pathfinding validator integration.
	•	ExecutionManager hooks for cycle watching, memory attach, and readiness checks.

📡 Sync & Drift Detection
	•	gnoman sync: reconcile secrets across keyring, .env, .env.secure, and remote vaults.
	•	Detect drift and resolve conflicts interactively.

📟 Dashboard UI
	•	Curses-powered neon cockpit.
	•	Views: diffs, branches, GitHub status, Safe states, audit logs.
	•	Keyboard-driven interactive ops (submit tx, rotate key, reconcile secrets).

⸻

🔧 Installation

From PyPI:

pip install gnoman-cli

From DockerHub:

docker pull gadgetsaavy/gnoman:latest
docker run -it gadgetsaavy/gnoman

From Source:

git clone https://github.com/74Thirsty/gnoman-cli.git
cd gnoman-cli
pip install -e .


⸻

🕹️ Usage

CLI

gnoman safe deploy --owners 0xA.. 0xB.. 0xC.. --threshold 2
gnoman wallet derive --path "m/44'/60'/0'/0/1337"
gnoman sync
gnoman audit --output report.pdf

Dashboard

gnoman tui

Navigate with arrow keys. q to quit.

⸻

🔒 Security Posture
	•	All secrets loaded from keyring-first (never plaintext by default).
	•	Forensic logs signed with GNOMAN’s audit key.
	•	Ephemeral execution to prevent key leakage.
	•	Multisig-first design: never trust a single key.

⸻

🛠️ Roadmap
	•	Remote vault sync (Hashicorp Vault, AWS Secrets Manager).
	•	ML-based anomaly detection in audit mode.
	•	zk-proof attestation of audit reports.
	•	Direct Flashbots bundle submission from dashboard.

⸻

🧑‍💻 Authors

Built with obsession by Christopher Hirschauer (74Thirsty).

⸻
