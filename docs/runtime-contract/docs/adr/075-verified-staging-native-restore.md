# ADR 075: Verify snapshot staging before native recovery publication

Status: Verified development candidate. All 1560 Windows unit tests pass on the
frozen input revision. After three fixture files gained explicit platform/clock
and repository input corrections, installed Runtime checks pass 267 cases on
each Windows/Linux profile and public-only Seed recovery consumers pass 39 on
each. Runtime bytes are unchanged between those cohorts. Evidence:
`reports/restore-boundary-v4-input/verification.json`. Full release gates remain open.
Public RPC/SDK API stays 1.15.0; no DDL or frozen permission word is added.

## Observed failures

The old restore trusted manifest paths, accepted duplicate aliases and ignored
several snapshot identity/boundary claims. It copied files into the final data
directory before SQLite/doctor validation and never rehashed the copied files.
Eight regressions reproduced traversal, duplicates, identity mismatch and a
post-copy byte change: `reports/backup-restore-boundary-baseline.xml`.

The doctor also checked only `artifact_blobs`, overlooking ordinary content
registered directly on `artifacts`, including bootstrap and public Artifact
outputs. A rewritten backup-file hash could consequently conceal changed CAS
bytes. Both registration paths now require their immutable content hashes.

## Native operator boundary

`agent-meta-restore --source <absolute-backup> --data-dir <absolute-target>` is a
separate native bootstrap entry point, like native credential provisioning.
The ordinary `agent-meta` CLI continues to use public RPC. Recovery cannot use a
daemon or signing key from a target that does not yet exist. Filesystem owner
access to a private backup authorizes this native recovery operation; model
tools never receive native paths, key material or a restore operation.

Only absent/empty targets are accepted, and source/target must not overlap.
There is no merge, force overwrite or live-owner replacement. No backup bytes,
keys, ciphertext or untrusted exception text enter console output. JSON uses
`runtime-restore/v1` and stable existing error/exit codes. Non-Windows fixture
key files require explicit `--insecure-dev-credential-file`; this does not
provide a production Credential Store profile.

## Verification and publication

Manifest v1 is closed, bounded and checked before copying: 16 MiB, 65,536 files,
4,096 UTF-8 bytes/64 components per relative path and 64 KiB credential-store
metadata. Producer backups enforce the same bounds. Only `meta.db` and normal
files beneath `artifacts`, `keys` or `backend` are restored. Reject absolute or
parent paths, backslashes/ADS, empty/dot components, Windows device/trailing
aliases, duplicate case aliases and file/parent collisions. Refer to
[Microsoft naming rules](https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file).
Observed symlink/reparse components are refused on source, target and input
files. Source directories and credential paths retain owner-only protection.

Copy to an exclusive private sibling staging directory. Recheck every staged
file's size/hash, SQLite/application/migration integrity, Realm/Epoch/meta/fact
boundary and all active CAS content before publication. Resolve bootstrap
signing credentials only through scoped Credential Store use, compare derived
public identities with committed bootstrap data, and require metadata agreement.
Re-init and restore share that credential verification. Missing, mismatched,
wrong-purpose or unavailable material must leave the target unpublished.

Quarantine interrupted operation rows and append the restore Fact in staging,
using canonical `transaction://` IDs and the hash of the originally read
manifest. Recheck the resulting chain, ensure the observed target is still
empty, then rename the complete tree into place. Failure removes only the
verified private staging child and preserves an existing empty target when
publication fails. This is complete-tree publication under the native private
owner model, not an adversarial filesystem-race or hardware power-loss proof.

## Evidence required

Include actual native Windows junctions/Linux symlinks, copied-byte changes,
manifest aliases/types, corrupt DB/CAS, omitted signing keys, empty/occupied
targets, failed publication, preserved signing identity and full fact-chain
verification. Native console proofs must run from an installed wheel.
Independent Seed must create a session through its signed tools, observe backup
refusal while live, release through the public Host, create a backup through the
public operations API/CLI, restore through this native entry point, then inspect
history and execute a fresh empty Scratch session through public SDK/CLI only.
No private DB/CAS/key/workspace inspection can substitute for that consumer.

The preceding Provider pin/full Seed 392-case result remains its own immutable
checkpoint. This candidate does not close S04/S05 release, remaining certificate
and fault coverage, S06 or S07.
