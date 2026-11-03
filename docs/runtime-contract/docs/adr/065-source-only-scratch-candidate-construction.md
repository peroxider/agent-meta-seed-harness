# ADR 065: Source-only Scratch candidate construction

Status: private source-only construction verified in development.
Public Scratch Host admission, persistence and S05/RP-04 remain open.

The legacy Scratch export helper cannot be the product validator: it subtracts
all module-bound names from free variables, conflates nested lexical scopes and
accepts duplicate selected definitions. Its behavior is retained as historical
legacy behavior; the new construction path never consults the live kernel.

Inputs are immutable, hash-verified cell Source Artifacts, explicit top-level
function/class names, a canonical Capability Contract Artifact, a canonical
dependency lock and the selected `scratch_candidate:<name>` entrypoint. Root
must independently authorize these inputs and verify their session/cell origin.
No pointer, closure, module object, pickle or C extension object is accepted.

Cell source follows §41.29: normalize CRLF/CR to LF before creating its Artifact,
encode UTF-8 without a BOM and preserve the presence/absence of its final newline.
The construction path refuses an already-addressed Source Artifact whose bytes
are not canonical. Source order is semantic; duplicate source references and
ambiguous definitions fail closed. Selected source segments include decorators,
including parenthesized/multiline decorators and UTF-8 column offsets. Only
selected definitions and top-level static imports are copied; unrelated module
assignments/expressions are not copied. All copied imports require lock evidence.
The generated module uses two LF separators and a final LF as its explicit
generation recipe; input Source Artifact bytes are never rewritten in place.

CPython 3.12 AST and compiler symbols validate lexical closure and the entrypoint.
For analysis only, list/set/dict comprehensions become generator-expression
scopes so PEP 709's optimization flags cannot misclassify module bindings.
Generated package files retain their selected source text. Native compilation
also checks invalid control flow; neither compilation nor construction executes
decorators, class bodies, imports or other supplied code. Hidden module values,
unselected definitions, unresolved globals, lambdas and dynamic import/compiler
forms are refused. Existing external-package source audit rules apply; its old
literal-import behavior remains the default for existing Harness packages, while
export explicitly selects the stricter static-import form.

The private `scratch-python-dependency-lock/v1` document has exactly:

```json
{"schema":"scratch-python-dependency-lock/v1","python_abi":"cp312","stdlib_modules":[],"wheels":[]}
```

Stdlib entries are explicit available import roots. Each wheel entry has exactly
`distribution`, `version`, `artifact_id`, and `modules`; distributions and module
lists are sorted/deduplicated. Root supplies the actual immutable wheel Artifacts
referenced by the lock. Hash, distribution/version metadata and import roots from
archive paths must agree. `top_level.txt` or type stubs alone are insufficient.
Wheel ZIP structure/paths, case/normalization collisions, symlinks, NUL truncation,
metadata ceilings, WHEEL headers and RECORD presence are checked without importing,
installing or extracting dependencies. Declared stdlib roots cannot be shadowed.
World materialization must still validate ABI/platform compatibility, dependency
resolution, RECORD contents and execution behavior; export is not that evidence.

Profile ceilings: 64 sources, 1 MiB per source/generated module/JSON input, 4 MiB
aggregate source, 50,000 AST nodes, 100 selections, 32 dependency wheels, 32 MiB
per wheel/64 MiB aggregate and 10,000 entries/1 MiB central directory per wheel.
Diagnostics are bounded and explicitly flag truncation. Other compiler ABIs and
unsupported source forms fail closed rather than guessing compatibility.

Success produces actual canonical AMPAK1 bytes, immutable input closure and a
separate provenance Artifact binding source IDs/order, exact selected spans,
imports, builtin dependencies, contract/lock/dependency IDs, generated file hashes
and the versioned analyzer/media type. Package constraints and the result fix
`trusted_candidate`; input metadata cannot elevate it. No Artifact is registered,
Fact committed, grant issued, Candidate installed or serving pointer changed by
this pure constructor. Root must publish/journal the result and use the required
Experiment/Promotion path; this is not the public `scratch.export-candidate/v1`
handler or an implementation of those governance gates.

The frozen Unicode/decorator/LF vector is shared by Windows/Linux installed
wheel tests. Tests separately execute only explicit test-owned pure fixtures
after construction to check reconstructed behavior. Side-effect canaries verify
that construction never executes selected class bodies or dependency imports.
