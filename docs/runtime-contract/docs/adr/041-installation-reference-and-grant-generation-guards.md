# ADR 041: Installation reference and grant generation guards

Date: 2026-10-30
Status: accepted for implementation; independent lifecycle/release gates remain OPEN

## Problem

The independent Seed upgrade test completed the old Task and released the old
instances, but uninstall still failed because the realm served a different
installation. A realm-wide reference check makes §41.60.5's documented
install-new → activate → drain-old → uninstall-old flow impossible. It also
omitted State-owner and unsettled-effect guards. Separately, the old helper
revoked only the latest activation's grants, leaving older generations after
reactivation of the same installation.

## Decision

Uninstall checks references to the target installation's immutable ownership
closure, not unrelated work in its realm. Owned Compositions come from its
activation history and direct typed slot references to its package Artifact.
Owned Capability versions come from the registered descriptor/package binding.
The same command transaction checks desired/serving/realized refs, nonterminal
Tasks, live instances, State owners and unsettled Effects before any uninstall
write. Active instances are matched by Composition or exact descriptor revision,
so a new version of the same Capability ID does not falsely pin the old package.
Unsettled Effects include UNKNOWN and cannot be dismissed as terminal success.
State ownership is checked by explicit owner identity; no State contents or
arbitrary payload strings are searched. Shared Capability-owned State remains a
conservative pin until its ownership/lifecycle is resolved through RP-04.

Uninstall preserves immutable artifacts, Facts, Compositions, invocation history
and the no-resurrection name/version rule. It does not delete bytes or change
the current installation/serving generation. The frozen permission set and
protobuf fields are unchanged; this corrects §41.60.5 implementation behavior.

Lifecycle revocation covers all activation-scoped grant generations recorded for
the retiring installation. If the same installation is activated again, cutover
retires its older generations while preserving only the newly requested
Composition's grant set. Candidate activation failure still revokes only that
candidate's set. Explicit current Authority is checked on every subsequent call.

§41.60.4's immediate scoped-grant revocation at cutover remains in force. Old
Tasks retain their frozen package/Surface; confirmed results can complete drain,
but a subsequent effect requiring revoked grants fails AUTHORITY_DENIED. It must
not borrow the new installation's grants or the Runtime bootstrap grant.

The development Host profile records this lifecycle behavior so recovery does
not silently change authorization semantics for an older incompatible Task.

## Proofs

Required Runtime tests cover owned and unrelated refs, State/effect pins,
descriptor-version distinction, old-generation revocation and preserved current
grants. Independent Seed lifecycle tests cover successful new-version cutover,
confirmed old Task drain/uninstall, rejected post-cutover old tool dispatch and
failed candidate preservation of serving/authority. These are development
proofs, not automatic RP-00/RP-07 or release verification.
