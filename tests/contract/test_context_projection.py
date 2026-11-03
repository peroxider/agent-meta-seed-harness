"""SH-CTX-01: independent package + real public-wheel Context enforcement.

The signed consumer fixture requests deliberately forged projections. It never
changes Runtime state or its readiness and imports only the published SDK.
"""

import asyncio
import json

from agent_meta_runtime.sdk import connect
from agent_meta_runtime.sdk.host import JsonPart, TerminalResult, TextPart, encode_terminal_result
from agent_meta_runtime.sdk.packages import canonical_json, sha256_hex
from agent_meta_runtime.sdk.context import SECTION_DELIMITER

from seed_package import install_seed, seed_bundle, wait_ready
from seed_runtime import admin, daemon_process, running_daemon


CONTEXT_PROBE = b'''
from dataclasses import replace
import json
from agent_meta_runtime.sdk.context import build_projection_input, rendered_sections

async def project(task, host):
    request = build_projection_input(task)
    value = json.loads(task.input_content)["value"]
    if value.startswith("forge-"):
        kind = value[len("forge-"):]
        if kind in ("content", "count", "renderer"):
            original = request.sections[1]
            changes = {"content": {"content": b'"unredacted"', "token_count": 12},
                "count": {"token_count": original.token_count + 1},
                "renderer": {"renderer_artifact_id": request.policy_artifact_id}}[kind]
            request = replace(request, sections=(request.sections[0], replace(original, **changes), *request.sections[2:]))
        elif kind == "policy":
            request = replace(request, policy_artifact_id=request.redaction_policy_artifact_id)
        elif kind == "source":
            request = replace(request, source_refs=request.source_refs[1:])
        elif kind == "budget":
            request = replace(request, budget_tokens=request.budget_tokens + 1)
    projection = await host.project_context(request)
    if value == "repeat-context-100":
        expected_hash = projection.manifest.identity_hash()
        expected_bytes = projection.rendered_content
        assert [s.section_id for s in projection.manifest.sections] == ["system", "task_input", "capability_schema", "state_summary", "facts"]
        assert projection.manifest.total_tokens == len(expected_bytes) <= 16384
        assert json.loads(rendered_sections(projection)["task_input"])["value"] == value
        assert any(ref.kind == "constitution" for ref in projection.manifest.source_refs)
        assert any(ref.kind == "runtime" for ref in projection.manifest.source_refs)
        assert len({s.renderer_artifact_id for s in projection.manifest.sections}) == 5
        for _ in range(99):
            replayed = await host.project_context(build_projection_input(task))
            assert replayed.manifest.identity_hash() == expected_hash
            assert replayed.rendered_content == expected_bytes
    return projection
'''


def test_real_host_rejects_six_forged_contexts_and_replays_frozen_context_100_times(tmp_path):
    bundle, publisher = seed_bundle(overrides={"agent_meta_seed_harness/context.py": CONTEXT_PROBE})
    with running_daemon(tmp_path, publishers=[publisher]) as data_dir:
        install_seed(data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(data_dir))
        cases = [("forge-" + kind, "FAILED") for kind in ("content", "count", "renderer", "policy", "source", "budget")]
        cases.append(("repeat-context-100", "SUCCEEDED"))
        for value, status in cases:
            path = tmp_path / "task-input.json"
            path.write_bytes(canonical_json({"provider": "fake", "scenario": "terminal", "value": value}))
            reference = admin(data_dir, "artifact", "put", str(path), "--kind", "task_input")["artifact_id"]
            task = admin(data_dir, "task", "submit", "--input-artifact", reference)
            async def observed():
                client = await connect(data_dir)
                try:
                    result, terminal = await client.wait_task(task["task_id"], timeout_s=10)
                    assert terminal and result["status"] == status, result
                    graph = await client.why(task["task_id"])
                    invocations = [node for node in graph["nodes"] if node.startswith("invocation://")]
                    execution = await client.get_task_execution(task["task_id"])
                    assert sorted(item["invocation_id"] for item in execution["invocations"]) == sorted(invocations)
                    if status == "FAILED":
                        assert result["error"] == "INVALID_RESULT" and not invocations
                    else:
                        assert len(invocations) == 1
                        assert len(execution["projections"]) == 1
                        assert execution["projections"][0]["manifest"]["total_tokens"] <= 16384
                        assert execution["consumed_budget"]["model_calls"] == 1
                        stored = execution["projections"][0]
                        manifest_content = canonical_json(stored["manifest"])
                        manifest_id = "artifact://sha256/" + sha256_hex(manifest_content)
                        assert await client.get_artifact_content(manifest_id) == manifest_content
                        bodies = []
                        for section in stored["manifest"]["sections"]:
                            body = await client.get_artifact_content(section["output_artifact_id"])
                            assert len(body) == section["token_count"]
                            assert section["output_artifact_id"] == "artifact://sha256/" + sha256_hex(body)
                            bodies.append(body)
                        rendered = await client.get_artifact_content(stored["rendered_artifact_id"])
                        assert rendered == SECTION_DELIMITER.join(bodies)
                        assert len(rendered) == stored["manifest"]["total_tokens"]
                        expected = TerminalResult((TextPart(value), JsonPart({"provider": "fake"}), TextPart("done")))
                        assert result["result_artifact_id"] == "artifact://sha256/" + sha256_hex(encode_terminal_result(expected))
                finally:
                    await client.aclose()
            asyncio.run(observed())


def test_projection_provenance_is_identical_across_tasks_and_restarts(tmp_path):
    """SH-CTX-01 beyond one frozen Task's 100 replays: distinct Tasks and a
    fresh daemon generation share the exact provenance frame, and every
    provenance reference resolves to its content-addressed artifact."""
    bundle, publisher = seed_bundle()

    def provenance(stored, input_reference):
        manifest = dict(stored["manifest"])
        # Per-projection identity/time fields are expected to differ, as are
        # the aggregate token total and the meta revision that advances with
        # unrelated meta mutations between submissions.
        for key in ("projection_id", "created_at_us", "x_identity_hash",
                    "x_request_hash", "x_task_id", "total_tokens", "meta_revision"):
            manifest.pop(key, None)
        sections = [dict(section) for section in manifest["sections"]]
        task_input = sections[1]
        task_input.pop("output_artifact_id")
        task_input.pop("token_count")
        manifest["sections"] = sections
        # The source set carries the Task's own distinct input Artifact, and
        # fact/runtime references are generation-scoped UUIDs; normalize both
        # so the comparable frame is the stable content provenance.
        manifest["source_refs"] = [
            ref["kind"] + ":" + ref["content_hash"] if not ref["ref"].startswith("artifact://")
            else ref["ref"]
            for ref in manifest["source_refs"] if ref["ref"] != input_reference]
        manifest["source_refs"] = sorted(manifest["source_refs"])
        return manifest

    with daemon_process(tmp_path, publishers=[publisher], label="first") as owner:
        install_seed(owner.data_dir, tmp_path, bundle)
        asyncio.run(wait_ready(owner.data_dir))

        async def project(value):
            client = await connect(owner.data_dir)
            try:
                path = tmp_path / f"input-{value}.json"
                path.write_bytes(canonical_json(
                    {"provider": "fake", "scenario": "terminal", "value": value}))
                reference = admin(owner.data_dir, "artifact", "put", str(path),
                    "--kind", "task_input")["artifact_id"]
                task = admin(owner.data_dir, "task", "submit", "--input-artifact", reference)
                result, terminal = await client.wait_task(task["task_id"], timeout_s=10)
                assert terminal and result["status"] == "SUCCEEDED", result
                execution = await client.get_task_execution(task["task_id"])
                stored = execution["projections"][0]
                rendered = await client.get_artifact_content(stored["rendered_artifact_id"])
                bodies = [await client.get_artifact_content(section["output_artifact_id"])
                    for section in stored["manifest"]["sections"]]
                assert rendered == SECTION_DELIMITER.join(bodies)
                return stored, rendered, reference
            finally:
                await client.aclose()

        async def resolve(stored):
            client = await connect(owner.data_dir)
            try:
                manifest = stored["manifest"]
                references = {manifest["policy_artifact_id"],
                    manifest["redaction_policy_artifact_id"]}
                references.update(section["renderer"] for section in manifest["sections"])
                for reference in references:
                    content = await client.get_artifact_content(reference)
                    assert sha256_hex(content) == reference.rsplit("/", 1)[1]
                for ref in manifest["source_refs"]:
                    if ref["ref"].startswith("artifact://sha256/"):
                        assert ref["content_hash"] == ref["ref"].rsplit("/", 1)[1]
                        content = await client.get_artifact_content(ref["ref"])
                        assert sha256_hex(content) == ref["content_hash"]
                    else:
                        # fact/runtime references are generation-scoped UUIDs
                        # bound to a content hash, not public Artifacts.
                        assert len(ref["content_hash"]) == 64
                        assert not ref["ref"].startswith("artifact://")
            finally:
                await client.aclose()

        alpha, alpha_rendered, alpha_input = asyncio.run(project("alpha"))
        beta, beta_rendered, beta_input = asyncio.run(project("beta"))

        async def compare_bodies():
            client = await connect(owner.data_dir)
            try:
                first = await client.get_artifact_content(
                    alpha["manifest"]["sections"][1]["output_artifact_id"])
                second = await client.get_artifact_content(
                    beta["manifest"]["sections"][1]["output_artifact_id"])
                assert first != second
                assert json.loads(first)["value"] == "alpha"
                assert json.loads(second)["value"] == "beta"
            finally:
                await client.aclose()

        # Distinct Tasks share the entire frozen provenance frame; the only
        # per-Task differences are the task_input section body and the Task's
        # own input Artifact inside the source set.
        alpha_refs = {ref["ref"] for ref in alpha["manifest"]["source_refs"]}
        beta_refs = {ref["ref"] for ref in beta["manifest"]["source_refs"]}
        assert alpha_refs.symmetric_difference(beta_refs) == {alpha_input, beta_input}
        assert alpha_input in alpha_refs and beta_input in beta_refs
        assert provenance(alpha, alpha_input) == provenance(beta, beta_input)
        sections = alpha["manifest"]["sections"]
        assert [section["section_id"] for section in sections] == [
            "system", "task_input", "capability_schema", "state_summary", "facts"]
        asyncio.run(compare_bodies())
        asyncio.run(resolve(alpha))
        owner.process.kill()
        owner.process.wait(timeout=10)
    with daemon_process(tmp_path, publishers=[publisher], label="second") as recovered:
        asyncio.run(wait_ready(recovered.data_dir))
        alpha2, alpha2_rendered, alpha2_input = asyncio.run(project("alpha"))
        # The same input projects byte-identically in a fresh daemon
        # generation under the same frozen serving revision — the whole
        # manifest minus per-projection identity/time fields.
        assert alpha2_input == alpha_input
        assert alpha2_rendered == alpha_rendered
        assert provenance(alpha2, alpha2_input) == provenance(alpha, alpha_input)
        assert alpha2["manifest"]["sections"] == alpha["manifest"]["sections"]
