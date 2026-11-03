# Installed native Context verification

Runtime Public API 1.16 can prepare a Task's frozen Context using an explicitly
supplied, pinned GLM-5.3-Flash native text encoder. Seed uses only
`await host.project_context()` and ordinary public SDK/CLI inspection. The
vocabulary, native encoder object and operator file path do not enter AMPAK or
Task DTOs. Native packages declare Public API >=1.16; default UTF-8 packages
retain their existing compatibility requirement.

The optional job uses Seed's fake Provider. It verifies actual native Root
encoding against independent Seed encoding of every stored section and the
complete rendered Context, including non-additive token boundaries and
redaction. A second actual Task omits the native input and must fail before any
model Invocation or projection. Neither synthetic counters nor a skipped test
can substitute for these two cases.

## Offline command

First install both explicit, non-editable wheels and the project's hash-locked
dependencies in a fresh environment. On Windows, install the optional binary
lock with `--no-index --find-links wheelhouse --require-hashes -r
package/provider-tokenizer-windows.lock`. The optional wheelhouse must already
contain every declared binary. Linux needs an independently prepared Linux
binary lock; Windows native wheel hashes do not establish Linux inputs.

Supply the author's public `tokenizer.json` of 20,217,442 bytes and SHA-256
`19e773648cb4e65de8660ea6365e10acca112d42a854923df93db4a6f333a82d`.
The command does not discover a local cache or download assets:

```console
python -I scripts/verify_native_context.py --runtime-wheel wheelhouse/agent_meta_runtime-0.1.0.dev1-py3-none-any.whl --seed-wheel dist/agent_meta_seed_harness-0.1.0.dev1-py3-none-any.whl --tokenizer-json /explicit/public/tokenizer.json --label native-context-unique
```

The supplied Runtime wheel must match `docs/ci-inputs.json`. Both actual
installations must match their explicit wheels, and Seed package bytes must
match the source under test. The pinned `tokenizers==0.23.3` engine is required.
All explicit input checks precede output creation. A bounded subprocess runs
only `tests/acceptance/native_context_probe.py`; default test discovery does
not silently skip an unavailable vocabulary or make the asset mandatory for
the minimal package.

`reports/<label>/run.json` records platform, wheel/package hashes, source input
hashes, engine/vocabulary identity and the two required executed cases. Source,
vocabulary and installed package bytes are checked again after execution. The
directory contains a verified copy of the public vocabulary, JUnit and logs;
it is local evidence and must not be committed. Failed runs remain FAILED and
an existing label is refused, preserving previous evidence.

## Scope

This proves local native Context text counting. It does not prove the custom
gateway's complete message/tool conversion, reasoning continuation or request
token counting. Usage/entitlement settlement, captured R2, real live Task
acceptance and release gates remain separate. The receipt keeps
`gateway_request_counting_verified`, `s04_complete` and `release_complete`
false. No upstream model request or incremental charge is incurred.

The text-encoding preparation receipt remains a separate, narrower artifact;
its original Host-availability fields must not be rewritten to imply this
installed Host test was performed at the time of preparation.
