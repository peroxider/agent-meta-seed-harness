"""RP-04 preparation: public-wheel ordinary content, never private storage."""

import asyncio

import pytest

from agent_meta_runtime.sdk import ErrorCode, StableError, connect
from agent_meta_runtime.sdk.packages import sha256_hex

from seed_runtime import admin, running_daemon


@pytest.fixture(scope="module")
def content_runtime(tmp_path_factory):
    root = tmp_path_factory.mktemp("ordinary-content")
    with running_daemon(root) as data_dir:
        yield data_dir, root


@pytest.mark.parametrize("content", [b"", b"\x00\x1a\xff\r\n", bytes(range(256)) * 4096])
def test_installed_wheel_sdk_and_cli_return_exact_ordinary_bytes(content_runtime, content):
    data_dir, root = content_runtime
    path = root / "consumer-input.bin"
    path.write_bytes(content)
    reference = admin(data_dir, "artifact", "put", str(path), "--kind", "data", "--media-type", "application/octet-stream")["artifact_id"]
    assert reference == "artifact://sha256/" + sha256_hex(content)
    async def observed():
        client = await connect(data_dir)
        try:
            before = await client.get_view()
            assert await client.get_artifact_content(reference) == content
            assert (await client.verify_artifact(reference))[0]
            after = await client.get_view()
            assert before["meta_revision"] == after["meta_revision"]
        finally:
            await client.aclose()
    asyncio.run(observed())
    value = admin(data_dir, "artifact", "content", reference)
    assert value == {"artifact_id": reference, "size_bytes": len(content), "content_hex": content.hex()}


def test_oversized_content_has_explicit_public_limit(content_runtime):
    data_dir, root = content_runtime
    path = root / "oversized-input.bin"
    path.write_bytes(b"x" * (1024 * 1024 + 1))
    reference = admin(data_dir, "artifact", "put", str(path), "--kind", "data")["artifact_id"]
    async def observed():
        client = await connect(data_dir)
        try:
            with pytest.raises(StableError) as error:
                await client.get_artifact_content(reference)
            assert error.value.code == ErrorCode.RESOURCE_EXHAUSTED
            assert "storage_relpath" not in error.value.details
        finally:
            await client.aclose()
    asyncio.run(observed())


def test_unknown_and_invalid_artifact_ids_fail_through_public_sdk(content_runtime):
    data_dir, _ = content_runtime
    async def observed():
        client = await connect(data_dir)
        try:
            for reference, code in (("artifact://sha256/" + "f" * 64, ErrorCode.NOT_FOUND), ("not-an-artifact", ErrorCode.INVALID_ARGUMENT)):
                with pytest.raises(StableError) as error:
                    await client.get_artifact_content(reference)
                assert error.value.code == code
        finally:
            await client.aclose()
    asyncio.run(observed())
