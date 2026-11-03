# ADR 074: Validate Provider feature fields at protocol positions

Status: Affected-scope installed development proof verified. Windows passed 281
Runtime Provider cases; Linux passed 279 with two actual Windows DPAPI cases
explicitly skipped. Independent Seed Provider consumers passed 80 cases on each
platform. Full project/live/release gates remain open. Public API remains 1.15.0.
Evidence: `reports/provider-business-fields-v1-input/verification.json`.

## Problem

After the Messages request shape check, `ProviderProfile.preflight` recursively
searched every JSON object for `thinking`, `cache_control` and `server_tool`.
It consequently rejected legitimate tool argument data and JSON Schema property
names. A signed Seed Provider could complete a model call and Artifact tool,
then fail its next model call before send solely because the confirmed tool
arguments used one of these ordinary business names.

The new three-case unit regression failed against the preceding source. A real
independent Seed native consumer on the pinned `c5a173db…11d7` wheel also failed
with FAILED_PRECONDITION after an Artifact tool stored such application data.
Original reports are retained as `reports/provider-business-fields-baseline.xml`
and Seed `reports/provider-business-fields-installed-baseline.xml`.

## Decision

Use the existing closed structural Messages validator for protocol positions.
Request root fields must match the frozen parameter allowlist. Message objects,
system/text/tool-use/tool-result blocks, tool definitions and tool choice retain
their explicit field/type checks. Actual thinking/server-tool blocks and cache
extensions at those positions remain unsupported. Do not interpret arbitrary
tool `input`, JSON Schema property names, descriptions or text as protocol
feature switches.

Remove the redundant recursive key-name scan. Token counting and firm maximum
cost preflight remain mandatory and unchanged. Original-wire response usage
validation, unknown liability, credential/egress enforcement and no-retry policy
remain unchanged. This compatible correction adds no supported reasoning,
caching, server-tool billing, streaming, tokenizer or live gateway profile.

## Verification scope

The positive unit matrix exercises each protocol word in both a schema and
tool argument objects, including protocol-looking nested values. Nine negative
cases place the same words in actual tool definitions or content-block fields;
those must still fail. Existing unsupported content/billing/tokenizer/cost
tests remain required.

The independent signed Seed fixture uses an actual controlled TLS Provider,
protected test credential, public activation, real `seed.artifact.put`, and a
second model request. It checks exact business values in stored Artifact and
assistant history, exactly two authorized upstream requests, and original-wire
TEST-currency accounting. It imports no private Runtime implementation and
reads no private storage. All data and pricing are synthetic; external model
requests and incremental charges remain zero.

Cross-platform installed proofs must identify their frozen wheel/source/test
hashes. Earlier full unit and Seed checkpoints remain evidence for their exact
bytes; they are not relabelled as full runs of this candidate. S04 real model,
S05 full fault/release, S06 and S07 gates remain open.
