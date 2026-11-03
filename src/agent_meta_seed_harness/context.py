"""Deterministic frozen-input projection through the public Host facade."""

from agent_meta_runtime.sdk.context import build_projection_input


async def project(task, host):
    return await host.project_context(build_projection_input(task))
