"""Consumer-owned signing key; operator setup goes through public CLI only."""

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from agent_meta_runtime.sdk import CommandAuthority
from agent_meta_runtime.sdk.packages import canonical_json

from seed_runtime import admin


def create_actor(data_dir, *, permissions, max_uses=1000):
    key = Ed25519PrivateKey.generate()
    identity = admin(data_dir, "authority", "create-principal", "--kind", "AGENT",
        "--public-key-hex", key.public_key().public_bytes_raw().hex())
    flags = [item for permission in sorted(set(permissions)) for item in ("--permission", permission)]
    grant = admin(data_dir, "authority", "delegate", "--subject", identity["principal_id"], *flags,
        "--scope", canonical_json({"realm_id": "realm://main", "targets": [{"type": "REALM_ALL"}]}).decode(),
        "--constraints", canonical_json({"max_uses": max_uses}).decode())
    return CommandAuthority(identity["principal_id"], grant["grant_id"], key.sign)
