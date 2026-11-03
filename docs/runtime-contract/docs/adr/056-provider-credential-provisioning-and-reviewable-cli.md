# ADR 056: Native Provider credentials and reviewable configuration

Date: 2026-11-01
Status: API 1.9 operator workflow implemented; configured model execution OPEN

## Decision

`agent-meta-provider-credential` is a separate native enforcement entry point.
It requires an initialized Runtime and proves possession of the protected key
of the current Realm Epoch's active Root operator. Its read-only metadata check
verifies the Runtime database identity, active principal, active grant and
matching Epoch. It neither issues an ordinary Runtime command nor consumes an
Authority use. Creating a credential item grants no model or binding authority.
The ordinary `agent-meta` CLI continues to use only public API operations.

The native entry point accepts either a noninteractive bounded stdin pipe or
an explicitly named Claude settings file. The latter reads only
`env.ANTHROPIC_AUTH_TOKEN`; it does not adopt the endpoint, model, other
environment settings or an implicit default file. The token is never an argv
option, environment injection, Fact, Artifact, public DTO or output value.
Diagnostics do not echo arbitrary argument values or source contents. Output
contains only an opaque UUIDv4 handle, purpose and credential security profile.
Mutable input and scoped-use buffers are cleared on exit. Python JSON parsing
can create immutable string copies; this is best-effort buffer hygiene, not a
guarantee of complete process-memory erasure.

Provider items live under `keys/providers/<sha256(RealmId)>`, with private
directories and item permissions. The hash identifies a public Realm, not a
secret. This separate store permits a worker to receive a Provider-only root
without access to Root or Service keys. Windows uses current-user DPAPI.
Non-Windows storage requires explicit insecure development opt-in and is
labelled `INSECURE_TEST_ONLY`; it supplies no product credential protection.
Data paths containing reparse points are refused.

Provisioning writes and reads back a new item in a private reserved staging
directory, then publishes the verified complete file with an atomic,
non-overwriting hard link. Unsupported storage fails closed. Failure cleanup
can delete only this call's newly published item, never a colliding item or the
previous handle. Rotation validates the old Provider handle, returns a fresh
one and retains the old item for frozen Tasks and backups. It does not change
any approved binding. Backup includes only complete published items, ignores
reserved `.provisioning-*` staging directories and restores all intermediate
key directories with private permissions. A restored DPAPI item still requires
the same applicable Windows user protection context.

## Public review and commit

API 1.9 adds the signed read-only query
`Harness.ValidateProviderConfiguration` using existing CommandRequest and
ResourceResponse messages. It validates the exact same payload, signature,
Root role, installation/profile/capability binding and current revision guards
as `Harness.ConfigureProvider`. It returns the reviewed payload, public model,
egress and pricing references and required authority. It performs no writer
transaction, command claim, Fact append or Authority-use reservation. The
preview explicitly says that no model will execute.

`agent-meta harness configure-provider` prepares a signed command and first
uses this query. With `--dry-run`, it returns that review and the exact signed
envelope for later execution. Without it, it submits the reviewed envelope to
the public mutation endpoint. The mutation checks its guards again in the
writer transaction; successful validation does not lock state or grant future
approval. A stale preview fails rather than rebinding newer state. A raw token
mistaken for a credential handle is rejected locally before a plan is printed.
The disable operation uses the same guarded public workflow.

The native import step and public approval step are deliberately separate
authorities: a published item is not an approval; an enabled approval is not
proof that a handle is provisioned or a model is executable. No public RPC can
read plaintext credential material. No proto field or SQL schema migration is
introduced.

## Evidence and limits

Tests exercise actual protected stores, isolated native CLI subprocesses,
atomic publication failures, rotation, backup/restore, buffer clearing,
cross-Realm and revoked operator refusal, bounded input and sanitized output.
Actual signed daemon IPC tests cover read-only validation, dry-run, executing
the exact reviewed command, disable and stale guards without side effects.
All credential material and profiles in these tests are synthetic.

The configuration-aware Root execution bridge, independent usage settlement
on that path, real exact tokenizer and price policy, EffectIntent/Managed
gates, captured R2 and explicitly bounded live verification remain open.
This change neither makes a paid request nor closes RP-03, and does not change
the independently pinned Seed Runtime wheel or its historical evidence.
