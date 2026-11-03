# Selected GLM reasoning contract gap

Reviewed against primary documentation on 2026-11-03. This is a contract gap
record, not an executable Provider profile or evidence about the configured
gateway. The existing terminal/v1 codec remains unchanged.

The [model author](https://docs.z.ai/guides/vlm/glm-5.3-flash) requires thinking
for GLM-5.3-Flash. Its [thinking guide](https://docs.z.ai/guides/capabilities/thinking-mode)
requires reasoning continuity across tool turns. Separately, Volcano's
[Messages documentation](https://docs.volcengine.com/docs/ark/messages-count-tokens-api?lang=zh)
describes opaque thinking signatures and preservation of their associated
content and order. These descriptions are protocol requirements to investigate;
they do not prove that this operator's custom gateway implements the same wire
shape, model limits or billing behavior.

## Public-contract work required

1. Freeze one observed, documented model/wire/usage profile. Do not enable a
   general “ignore unknown blocks” path or reinterpret reasoning as ordinary
   TextPart/tool arguments. Existing v1 content/usage rejection stays in place.
2. Define an explicit policy for any opaque upstream continuation that needs
   byte-preserving replay. A redacted ModelResponse cannot substitute for signed
   reasoning. Ordinary model history, tool dispatch, Fact diagnostics and
   default R2 fixtures must not receive private raw reasoning/signatures.
3. If exact continuation requires Restricted Raw retention, that mechanism
   needs a versioned Root-owned storage/access/retention/egress contract and
   explicit policy authorization. Raw retention is currently off. Package code
   must not write ad hoc files, bypass redaction, embed raw bytes in unrelated
   fields or claim a content hash proves access authority.
4. Bind continuation to the actual confirmed Invocation, Task, Provider profile,
   configuration revision and ordered tool results. Root must verify the final
   request before token/cost reservation and dispatch. Unknown effects after
   disconnect or crash must retain their existing no-resend behavior.
5. Verify all billable dimensions independently from original wire, including
   reasoning/cache dimensions where applicable. Unknown dimensions remain
   unknown and retain liability; a model-authored cost claim cannot settle them.
6. Supply the exact tokenizer implementation and pricing/entitlement policy for
   this gateway. An upstream token-count estimate or public model limit does
   not establish exact Host counting or the gateway's tariff. The current
   controlled TEST byte tokenizer cannot be used for the selected model.

Local tokenizer preparation now fixes the author's vocabulary/template/config
and `tokenizers==0.23.3`; real native text vectors are verified offline. The
single default-template prompt count of 17 matches the operator diagnostic.
That sample does not establish the gateway's full message/tool conversion or
the enforced Root/Context tokenizer path. See
[the preparation contract](provider-tokenizer-preparation.md).

## Independent proof required

Use synthetic controlled-loopback fixtures first: interleaved reasoning/tool
order, opaque-signature preservation, altered/missing/reordered continuation,
profile/Task/Actor/configuration substitution, retention disabled, redaction,
budget overrun, accepted disconnect, cancellation, late response and crash.
Only confirmed terminal results can authorize tool dispatch. The tests must
observe real public SDK/CLI behavior rather than construct private store rows.

Live verification additionally requires a demonstrated subscription/free-quota
boundary with zero incremental charges and no paid fallback. The operator has
confirmed that quota-only boundary and authorized real requests; rate limiting
must stop validation. One bounded native operator diagnostic returned HTTP 200
with `thinking` followed by `text`, `end_turn`, exact model match and final `OK`.
It reported input/output tokens 17/17, zero cache-read tokens, absent cache-creation
tokens and two unrecognized usage fields. Raw reasoning, signatures and field
names were not retained, so this is neither captured R2 nor a tool-continuation
proof. The custom gateway's complete codec and independent billing measurement
remain unverified. See `reports/provider-wire-observation-v1/verification.json`. No test,
prompt limit or zero-valued local price can establish the operator's upstream
billing entitlement.
