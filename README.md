# GNOMAN — Universal Keyring Manager

GNOMAN is a cross-platform command line tool that inspects and maintains the
secrets stored in your operating system keyring. It provides a consistent
interface across Linux (Secret Service), macOS (Keychain) and Windows
(Credential Locker) so that you can audit, export, rotate and restore
credentials without leaving the terminal.

## Features

- 🔍 **Enumerate every keyring entry** regardless of namespace or application.
- 🧾 **Inspect and audit** secrets for stale credentials, missing metadata and
  duplicates.
- ✍️ **Create, update or delete** entries using the native system backend.
- 📦 **Encrypted export/import** routines for disaster recovery and migration.
- ♻️ **Credential rotation** that generates high-entropy replacements in bulk.

## Installation

Install GNOMAN from PyPI:

```bash
pip install gnoman-cli
```

## Usage

```
usage: gnoman [-h] [--gui] [--version] {list,show,set,delete,export,import,rotate,audit} ...
```

Pass the optional ``--gui`` flag to launch a lightweight Tkinter desktop interface focused on
secret management.

### List keyring entries

```bash
gnoman list --namespace github
```

### Show a secret

```bash
gnoman show github.com personal-token
```

### Set or update a secret

```bash
gnoman set github.com personal-token
```

You will be prompted for the secret value when it is not provided directly.

### Export and import

```bash
gnoman export backup.gnoman
# ... later ...
gnoman import backup.gnoman
```

Both operations prompt for a passphrase unless `--passphrase` is supplied.

### Rotate credentials

```bash
gnoman rotate --services github.com,slack
```

Regenerates high-entropy secrets for the selected services.

### Audit

```bash
gnoman audit --stale-days 90
```

Produces a JSON report summarising duplicates, stale entries and other
potential issues.

## Development

Tests exercise the platform-agnostic logic using the in-memory adapter:

```bash
pip install -e .[dev]
pytest
```

The CLI interacts with the system keyring by default. Within unit tests the
`gnoman.utils.keyring_backend.use_adapter` helper swaps in an in-memory backend
to avoid touching real credentials.
