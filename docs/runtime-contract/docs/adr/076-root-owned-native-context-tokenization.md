# ADR 076: Root-owned local Context tokenization

Status: Implemented development candidate; installed native and full regression
verification is in progress. No product profile is released.

Public SDK/Host API advances to 1.16.0. No entity, DDL, permission word or RPC
method is added. Older explicit `ProjectionInput` calls remain supported.

## Native data and authority

`agent-meta start --context-tokenizer-json FILE` is an explicit native operator
input. It reads at most 20,217,443 bytes and accepts only the fixed public
GLM-5.3-Flash vocabulary of 20,217,442 bytes with SHA-256
`19e773648cb4e65de8660ea6365e10acca112d42a854923df93db4a6f333a82d`.
The [author revision](https://huggingface.co/zai-org/GLM-5.3-Flash/tree/46a050bec13002ad29ee795c16e61cf4fa3c4a9c)
is represented by the exact data hash and tokenizer ID. Hash/size verification
precedes parsing or optional library loading. `tokenizers==0.23.3` is required;
padding/truncation, URL/cache discovery and remote Python code are unavailable.
Missing or incompatible data/engine fails closed. The default daemon does not
load a native tokenizer or download any model assets.

The engine is a Root implementation dependency, supplied through a Root-only
counter port. The 20 MB vocabulary and the file path never enter Task DTOs,
AMPAK, Context projections or package callbacks. A closed
`context-tokenizer/v2` Artifact records model, algorithm, engine version and
vocabulary identity. Package metadata is data, not authority to choose code,
open files or replace Root's counter. Projection provenance includes the
immutable descriptor and renderer references. Changing a descriptor identity
cannot select another asset or implementation.

## Projection ownership and counting

`await host.project_context()` asks Root to apply the Task's already frozen
Context policy and sources. This does not let a caller choose a new profile,
source, renderer or implementation. The external Harness continues to author
policy/schema/renderer Artifacts. A facade carries only its opaque Task token;
no native encoder/store is exposed. Repeated projections preserve identity.

For a native descriptor, all five renderers must use the versioned
`context-renderer/v2` / `jcs-ladder-prefix-tokens/v1` contract. Normalization and
redaction still precede ranking and counting. Allocation measures actual
complete rendered prefixes, including delimiters, rather than assuming BPE
counts add across section boundaries. Negative prefix increments receive no
budget credit. Tail truncation uses bounded deterministic character-prefix
search and verifies every retained prefix; it does not promise a globally
maximal BPE prefix. The complete projection is independently counted again,
with both its token budget and a 1 MiB rendered-byte ceiling enforced.
Per-section counts need not sum to the full BPE count.

The pure SDK builder optionally accepts a counter for local authoring. This is
not an execution credential: Root independently selects its native counter and
recomputes all fields before accepting an explicit projection. A forged count
is INVALID_RESULT before model dispatch. The v2 section accessor checks frame
and content hashes; actual counts are enforced by Root. Model invocation still
requires the exact projection object issued by the same Task Host. A Task
terminal must still derive from its confirmed terminal model response.

## Compatibility and remaining gates

UTF-8 Context v1 policy/rendering remains unchanged. Native Context packages
declare Public API >=1.16 and require an explicit operator-supplied engine/data
input. Availability failures occur before a model invocation. The trusted
in-process profile still supplies no strong isolation or hard preemption.

This counts local Context text, not the selected gateway's entire model
request. It does not establish gateway message/tool templates, exact upstream
input counts, reasoning continuation, billable dimensions, pricing/entitlement
settlement, captured R2 or a production live Host. Those S04/RP-03 gates remain
open. No real gateway request or raw reasoning retention is enabled here.
