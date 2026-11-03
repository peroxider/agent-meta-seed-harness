"""Public typed Scratch plans; Runtime owns native workers and publication."""

import json

from agent_meta_runtime.sdk import ErrorCode, StableError
from agent_meta_runtime.sdk.host import (
    ScratchCreate,
    ScratchExecution,
    ScratchBindings,
    ScratchInspect,
    ScratchExportCandidate,
    ScratchRelease,
    ResourceAdapter,
    InvocationResult,
)


_PLANS = {
    "seed.scratch.create": (ScratchCreate, (), ("idle_ttl_us", "wall_ttl_us")),
    "seed.scratch.execute": (
        ScratchExecution,
        ("session_id", "source_artifact_id", "deadline_at_us"),
        ("timeout_us",),
    ),
    "seed.scratch.bindings": (ScratchBindings, ("session_id",), ()),
    "seed.scratch.inspect": (
        ScratchInspect,
        ("session_id",),
        ("name", "handle", "max_depth", "max_items", "max_bytes", "max_ms"),
    ),
    "seed.scratch.export_candidate": (
        ScratchExportCandidate,
        (
            "session_id",
            "source_artifact_ids",
            "export_names",
            "contract_artifact_id",
            "dependency_lock_artifact_id",
            "entrypoint",
        ),
        ("dependency_artifact_ids", "support_artifact_ids", "name", "version"),
    ),
    "seed.scratch.release": (ScratchRelease, ("session_id",), ()),
}


def prepare(request):
    try:
        constructor, required, optional = _PLANS[request.call.name]
        value = json.loads(request.call.arguments_json)
        if (
            type(value) is not dict
            or set(required) - set(value)
            or set(value) - set(required + optional)
        ):
            raise ValueError("arguments differ")
        if constructor is ScratchExportCandidate:
            for key in (
                "source_artifact_ids",
                "export_names",
                "dependency_artifact_ids",
                "support_artifact_ids",
            ):
                if key in value:
                    if type(value[key]) is not list:
                        raise ValueError("selection requires an array")
                    value[key] = tuple(value[key])
        return constructor(**value)
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise StableError(
            code=ErrorCode.INVALID_ARGUMENT, message="invalid Scratch tool intent"
        ) from None


def normalize(receipt):
    if (
        receipt.contract
        not in {
            "scratch." + operation + "/v1"
            for operation in (
                "create",
                "execute",
                "bindings",
                "inspect",
                "export",
                "release",
            )
        }
        or receipt.media_type != "application/json"
        or len(receipt.content) > 1024 * 1024
    ):
        raise StableError(
            code=ErrorCode.INVALID_RESULT, message="invalid Scratch receipt"
        )
    value = json.loads(receipt.content)
    if type(value) is not dict or "schema" not in value or "session_id" not in value:
        raise StableError(
            code=ErrorCode.INVALID_RESULT, message="invalid Scratch receipt shape"
        )
    return InvocationResult(content=receipt.content)


def adapters():
    return {name: ResourceAdapter(prepare, normalize) for name in _PLANS}
