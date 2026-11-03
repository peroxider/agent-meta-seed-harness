# ADR 044: Public ordinary principals and bounded delegation

Date: 2026-10-30
Status: accepted for implementation; Host/governance/release gates remain OPEN

## Decision

Public API 1.4 adds three signed mutations, using existing CommandRequest and
MutationResponse messages: `Authority.CreatePrincipal`, `Authority.Delegate`,
`Authority.Revoke`. They map respectively to the existing `authority.grant`,
`authority.delegate`, `authority.revoke` permissions. The 42-permission registry
and protobuf field numbers are unchanged. Each requires negotiated minor four.

CreatePrincipal binds an AGENT, CAPABILITY or PEER identity to exactly one raw
Ed25519 public key. It accepts a matching canonical PrincipalId or generates one
at commit. Existing identical identity is idempotent; changing a key/kind under
the same ID is refused. No private key, credential handle or implicit grant is
created or returned. OPERATOR_ROOT/SERVICE identities remain exclusively owned
by bootstrap/succession/runtime lifecycle. The new resource type is
`principal-identity/v1`, schema version one. The Fact catalog adds
`authority.principal_registered`, with a PrincipalId entity, before its use.

Delegate grants only to active, same-realm ordinary principals. Its parent is
the exact authority_grant_id signed in the envelope; callers cannot nominate a
different issuer. Permissions, typed scope, time/epoch/use constraints and
remaining delegation depth are checked by the existing delegation mechanism in
the same transaction. Input uses strict scalar/object fields, never bool/int
coercion. Child unbounded authority is not exposed. The result is the existing
`authority-grant/v1` resource with the immutable grant definition/status.
Nonempty resource_ceiling currently returns FEATURE_UNAVAILABLE before any
mutation: amount accounting is not implemented, so this endpoint does not
accept an unenforced limit. Effective remaining depth is the smaller of the
grant depth and its constraint; every child consumes one and cannot increase it.

Public delegation consumes one parent use, including its signed-command use.
The lower-level helper recognizes that exact already-reserved command use
instead of double charging. Harness activation still has a separate activation
command use and one reviewed batch delegation use. Other store callers retain
their existing delegation reservation behavior.

Revoke targets delegated grants held by ordinary principals in the same realm.
The caller must be an operator Root, the issuer, or the subject, in addition to
holding authority.revoke over the target grant's complete scope.
Root/bootstrap/runtime Service grants cannot be
revoked through this endpoint; their specialized recovery/lifecycle rules remain
unchanged. Revocation takes effect before every later model/tool authorization,
and it preserves prior uses and immutable command replay.

These entrypoints let independent consumers use their own generated signing
keys and scoped actors through public SDK/CLI. They do not export Runtime Root
credentials, create a second Root, implement Epoch succession, publish a Host
SPI support claim or close RP-01/RP-05/RP-07 by themselves.

## Proofs

Runtime proofs must cover actual signed create/delegate/revoke, immutable key
binding, forbidden system kinds, scope/permission/constraint/depth expansion,
one-use accounting, foreign/inactive/unknown subjects, revocation ownership and
old-minor refusal. Independent installed-wheel Host proofs must use only the
consumer's own keys, exercise actor-specific permission failure/revocation and
prove that Service or Root grants cannot substitute for the initiating actor.
