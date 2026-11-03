# Local GLM tokenizer preparation

This is S04 preparation, not an executable live Host profile. The default
minimal/tools packages do not include the new tokenizer utility in their signed
execution source closure. Runtime admission and its controlled-test tokenizer
are unchanged. SH-PROV-01/03 and RP-03 remain open.

## Frozen inputs

The installed Seed data resource
`data/provider-tokenizers/glm-5.3-flash-v1.json` fixes the
[model author's revision](https://huggingface.co/zai-org/GLM-5.3-Flash/tree/46a050bec13002ad29ee795c16e61cf4fa3c4a9c)
and SHA-256/size of four files: tokenizer JSON, tokenizer configuration, chat
template and MIT license. It also fixes the seven public encoding vectors by
hash and requires `tokenizers==0.23.3`. Unsupported engine versions, altered
files, missing inputs or mutable/non-byte input fail closed before parsing.

The 20,217,442-byte vocabulary is an explicit offline preparation input. It is
not embedded in the Seed wheel or silently fetched from a model cache. Builds,
imports and ordinary Tasks do not download model files. No model weights or
remote Python code are needed. The template is verified as data; this tool
does not execute it. The native engine loads only hash-verified JSON bytes,
without `from_pretrained`, URL fetching, padding or truncation.

The optional Windows/CPython 3.12 dependency closure is hash-pinned in
`package/provider-tokenizer-windows.lock`, separate from the default CI lock.
It contains binary wheels only. Prepare those wheels explicitly in an online
preparation phase, then install them offline. The optional dependency is never
needed by the minimal fake Provider or normal package build.

## Offline command

From an environment with the built Seed wheel, supply the four downloaded
author files in an explicit directory, the frozen vector file and an absent
output directory:

```console
python -m pip install --no-index --find-links <tokenizer-wheelhouse> --require-hashes -r package/provider-tokenizer-windows.lock
python -I scripts/prepare_provider_tokenizer.py --assets-dir <author-files> --vectors tests/fixtures/provider-tokenizer/local-encoding-v1.json --output-dir <new-output-directory>
```

The command verifies all inputs before creating its output, checks seven fixed
vectors twice, copies verified public assets and writes `verification.json` last.
It implements no download or network operation. The earlier installed native
verification additionally guarded Python socket/DNS APIs and checked five
invalid-text cases and two unsupported engine versions; those test guards are
not a claim of operating-system network isolation.
An I/O failure may leave an incomplete output directory without a receipt;
there is no overwrite or automatic retry. Existing output requires a different
explicit directory, not `--force`.

Text input is valid Unicode bounded to 1 MiB in UTF-8. Token IDs are returned as
immutable tuples, with `add_special_tokens=False`. Empty text stays empty;
multi-byte text is not counted by character or UTF-8 byte length. Special-token
strings follow the pinned tokenizer's literal encoding rules. This utility does
not authorize caller input or define escaping for a live message protocol.

## Evidence and limits

The independent Windows installed-wheel preparation is under
`reports/provider-tokenizer-native-v1`. It verifies actual native encoding,
including Chinese, combining characters, emoji, structured JSON and special
tokens. `test_provider_tokenizer_preparation.py` separately proves hash/size
substitution and fallback refusal without requiring the optional engine.

The current preparation CLI is separately frozen and installed under
`reports/provider-tokenizer-native-v2`. Its `reports/verification.json` verifies
both distributions' installed files, 17 optional wheels/608 installed files,
seven native vectors, five invalid texts, two unsupported versions and three
actual CLI refusals: existing output, altered vectors and missing engine.
The default full consumer does not install the optional tokenizer engine.
These remain local text-encoding checks with no Provider request or Host
admission claim.

The public diagnostic prompt encodes to five text tokens. Rendering that one
sample using the pinned author's default template produces 17 input tokens,
matching the existing gateway diagnostic's reported 17. This is one sample,
not proof of all gateway conversions, defaults or token accounting. The pinned
sample is a public golden; it is not a general Anthropic-to-GLM renderer.

Root still needs a versioned, enforced tokenizer/data-loading and Context
integration contract. The vocabulary exceeds the current Provider document
limit of 1 MiB, so it must not be smuggled into an unrelated Artifact or treated
as executable package input. The actual gateway's system/tool formatting and
reasoning continuation must be verified before firm request counting and
reservation. Context selection must use the same approved tokenizer. Complete
usage/pricing or quota-entitlement settlement, captured R2, formal live Task
acceptance and release evidence remain required.
