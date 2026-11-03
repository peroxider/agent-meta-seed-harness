"""Deterministic frozen-input projection through the public Host facade."""

from agent_meta_runtime.sdk.context import build_projection_input
import json


async def project(task, host):
    if task.context is not None:
        artifacts = dict(task.context.artifacts)
        profile = json.loads(artifacts[task.context.profile_artifact_id])
        descriptor = json.loads(artifacts[profile['tokenizer_artifact_id']])
        if descriptor.get('schema') == 'context-tokenizer/v2':
            return await host.project_context()
    return await host.project_context(build_projection_input(task))
