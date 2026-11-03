"""Shared public-only Scratch consumer result helpers."""

import json


def prior(index, *path):
    return {"$result": {"index": index, "path": list(path)}}


async def published(client, execution):
    return [
        json.loads(await client.get_artifact_content(row["output_artifact_id"]))
        for row in execution["invocations"]
        if row["kind"] == "CAPABILITY" and row["status"] == "SUCCEEDED"
    ]
