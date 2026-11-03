# ADR 058: Explicit native Provider test launch

Date: 2026-11-02
Status: native test launch implemented; production Provider gates unchanged

## Decision

The installed `agent-meta start --controlled-provider-test-ca <file>` native
launcher makes ADR 057's controlled assembly accessible to independent consumers
without importing Runtime implementation modules. This is an explicit startup
option, not a public mutation RPC or a package-selected execution profile.
The default startup and configuration behavior are unchanged. Public API remains
1.9; no proto field, SQL schema or ordinary Task facade is added.

The launcher reads at most 65537 bytes from an explicitly selected regular file,
rejects empty/oversized/unavailable input and parses the PEM trust material before
starting a daemon. The embedded assembly validates the same material. Invalid
input diagnostics never echo file contents. A dry-run reports
`provider_execution=CONTROLLED_TEST_ONLY` and starts neither store nor daemon.
Explicit InMemory plus this option is rejected, including during dry-run.

This launcher preserves every controlled assembly gate: a distinct Host profile
hash; loopback-only networks; synthetic `TEST` pricing; exact fixture tokenizer;
signed package/profile declaration; current Root-operator approval; protected
scoped credential metadata; atomic reservation and dispatch checks; certified
owned worker; and independent original-wire usage settlement. Native credential
provisioning remains a separate published enforcement console entry point using
bounded stdin or an explicitly selected settings source.

The CA file is public trust material, not a credential source. This option
does not accept a token, copy environment configuration, infer a tariff, permit
public HTTPS, widen an Actor grant or supply Managed isolation. A production
gateway cannot become supported by enabling this flag. Worker/network/backend
security claims remain as in ADR 057.

## Independent consumer path

Seed can now build an explicitly signed Messages package and select the test
launcher through the installed console entry point. Its ordinary application
callbacks receive only public immutable plans/responses. They never import
Runtime private modules, read Runtime keys/DB/CAS or select a transport. Test
credentials enter only the separate native provisioning process's stdin.
Root approval uses signed public configuration commands; ordinary task mutation
can use a consumer-owned Actor key with delegated scoped permissions.

This enables an independent synthetic integration check, not live upstream or
captured R2 evidence. Production placement/EffectIntent, exact real tokenizer and
gateway tariff, selected-model reasoning semantics, full recovery/release
evidence and RP-03 remain open. No production-support status is promoted.

## Validation

Installed CLI subprocess tests cover missing/directory/empty/oversized/invalid
PEM input before store creation, dry-run without daemon creation, conflicting
backend selection, actual native startup/SDK connection and signed shutdown.
The existing controlled daemon tests continue to cover the effect path and
its distinct profile hash.
