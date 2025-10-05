# GNOMAN Implementation Status

## Overview

This document inventories the current state of the GNOMAN CLI versus the production requirements outlined in the latest developer directive. The goal is to surface the functional gaps that prevent the existing codebase from satisfying the "bulletproof" bar described in the directive and to provide actionable next steps.

## Key Findings

1. **Safe / Guard Integration**
   * The command handlers in `gnoman/commands/safe.py` rely on the in-memory registry defined in `gnoman/services/state.py`. There is no bridge to an on-chain Gnosis Safe, no signing pipelines, and no DelayGuard deployment/validation logic.
   * Guardian/monitoring features have been removed from the CLI; there is no contract watcher, queue management, or enforcement of guard invariants.

2. **Wallet + Key Management**
   * Wallet operations draw from deterministic fixtures held in memory (`WALLET_INVENTORY`) rather than an encrypted keystore. AES-GCM encryption, password handling, and entropy validation are not implemented.
   * Key rotation, vanity search, and HD derivation utilities are mocked through deterministic pseudo-random generators.

3. **Secrets Synchronisation**
   * `SecretsStore` manages a shared dict of stores, but there is no integration with OS keyrings, Hashicorp Vault, AWS Secrets Manager, or `.env.secure` files. Error handling assumes ideal conditions.

4. **Forensic Logging**
   * `gnoman.utils.logbook` emits structured records, yet there is no tamper-evident append-only store nor signed audit trail. The existing `gnoman_audit.jsonl` file appears to contain sample data only.

5. **Testing Coverage**
   * The current pytest suite exercises the thin abstractions that exist today. It does not cover any real integrations, failure modes, or regression scenarios expected in a production deployment.

## Implications

Because of these gaps, the repository does not meet the directive's requirements. Attempting to ship or rely on the current code in a production incident-response workflow would be high-risk: there are no cryptographic assurances, no contract safety checks, and no validated guard logic.

## Recommended Path Forward

1. **Architecture Discovery**
   * Define concrete interfaces for Safe registries, transaction queues, guard daemons, and encrypted wallet stores. Replace the placeholder in-memory services with implementations that target real infrastructure (e.g., Web3.py + Safe contracts, SQLCipher, external secret stores).

2. **Incremental Hardening**
   * Implement AES-GCM encryption for wallet artifacts, including password derivation (PBKDF2/Argon2) and nonce management.
   * Stand up integration tests against forked Ethereum nodes (Anvil, Hardhat) to validate Safe interactions and DelayGuard behaviour.

3. **Observability & Auditability**
   * Build a cryptographically signed audit log (Ed25519 or secp256k1) and embed hash chaining for every state mutation.
   * Extend the CLI commands to emit explicit exit codes and rich error diagnostics.

4. **Risk Management**
   * Document operational runbooks for key rotation, incident response, and guard deployment. Codify rollback plans and failure alarms.

These steps are prerequisites before tackling the "every function and feature" mandate. Attempting to deliver the directive without this groundwork would lead to fragile, unauditable code.

