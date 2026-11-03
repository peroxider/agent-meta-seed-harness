# ADR 033: Signed local commands and protected operator credentials

Date: 2026-10-30
Status: accepted for implementation; full security/recovery release gates remain open

## Decision

Public API v1 keeps its existing methods and CommandEnvelope fields. The SDK
exports `CommandAuthority`, `encode_command`, `decode_command`, `sign_command`
and `AgentMetaClient.execute_command(method, envelope_jcs)`. A consumer can
persist an exact canonical envelope and resend it without minting another ID.
The signing callback receives only the signature preimage; no storage adapter
or private key is exported through the SDK. Canonical decoding requires the
complete field set, rejects duplicate fields and validates the Ed25519 encoding.

Every public mutation requires a registered signing Principal and an explicit
Grant. Root command signatures are required by §41.28. The same proof is also
required for Service/other Principals: a public Principal ID and Grant ID are
identifiers and cannot authenticate a caller. Signatures bind the existing
authorization hash, a nonce and an issue timestamp. Fresh commands accept a
five-minute clock window and a 16–256-byte nonce. Local OS peer identity is an
additional transport boundary; it never grants Realm authority.

The read-only admission preview and the check inside `BEGIN IMMEDIATE` enforce
Principal status, Grant subject/status/epoch/permission/scope/constraints and
optional expected Meta revision. One `command` use is reserved before mutation
in the same transaction; a failed mutation rolls back both. Distinct commands
cannot reuse a nonce, including when another writer wins after the preview.

Replay checks the original authorization identity before current Grant/revision
state. It still verifies the caller's signature, but does not reject the
original signature merely because its timestamp has aged. Revocation therefore
prevents new work while allowing recovery of a previously committed receipt.
Task submission reconstructs the original accepted handle from its durable
Task, independently of current serving readiness/revision. Backup and GC apply
admit the caller's original command into a durable Operation and never repeat
filesystem effects on an ambiguous retry. Interrupted Operations require
recovery; they are not treated as new requests.

The frozen 42-permission vocabulary is retained. Proposal creation maps to
`experiment.run`; candidate promotion and composition rollback map to
`composition.promote` and `composition.rollback`. The formerly advertised
`evolution.propose/promote/rollback` permission strings are not registry entries.
Runtime-owned experiment continuations use independent real Service identities
and command IDs; they never copy a caller signature onto altered command bytes.

## Credential storage

Windows initialization defaults to CurrentUser DPAPI with UI forbidden. A
protected DACL grants only the current user full access to credential storage;
directory ACEs inherit to children. Each encrypted envelope is bound by DPAPI
entropy to its exact opaque handle and purpose. Scoped reads zero their mutable
buffer on both success and exception. Rotation creates a separate item and
retains the old item until its explicit reference count is zero.

Local metadata contains Root/Service handles and public operator identity only.
Reinitialization verifies decryptability and matches both signing keys against
the committed public identities. Backup/restore reapplies explicit owner-only
protection; same-user restored DPAPI material must still sign successfully.
Cross-account migration requires an explicit recovery mechanism and is not
inferred from copying ciphertext.

Plaintext credential files require `--insecure-dev-credential-file` and report
`INSECURE_TEST_ONLY`. They do not satisfy a product security profile. A supported
non-Windows encrypted credential backend is not yet implemented; default init
there fails closed instead of silently selecting plaintext storage. Existing
legacy raw key files are not automatically trusted or migrated.

## Evidence and remaining work

Runtime unit evidence: `test_public_command_authority.py`,
`test_windows_credentials.py`, `test_bootstrap_init.py`,
`test_operations_backup_gc.py`, `test_local_server.py`, and `test_sdk_cli.py`.
These tests cover real Windows APIs and the local wire path, plus synthetic
negative/race cases. They do not establish cross-account isolation or a complete
provider credential/egress boundary.

Activation-plan binding and delegated activation Grants are specified and tested
in [ADR 034](034-signed-activation-plan-and-delegation.md). All-command stable
resource replay, full Host execution/recovery, secure non-Windows storage,
provider egress, and external installed-wheel recovery remain required work.
RP-00 through RP-07 and all External-Seed release IDs remain open. No release
profile or Harness Contract version is promoted by this ADR alone.
